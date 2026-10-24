from uuid import uuid4

import httpx

from app.models import IdempotencyRecord, OutboxEvent, Reservation
from app.parking_client import ParkingClient, ParkingResult


def idem(headers, value=None):
    return {**headers, "Idempotency-Key": value or str(uuid4())}


def test_create_is_confirmed_and_idempotent(client, db_session, fake_parkings, auth_headers, create_payload):
    key = str(uuid4())
    created = client.post("/api/v1/reservas", json=create_payload, headers=idem(auth_headers, key))
    assert created.status_code == 201
    body = created.json()["reservation"]
    assert body["status"] == "confirmed"
    assert body["ever_confirmed"] is True
    assert created.headers["Location"].endswith(body["id"])

    repeated = client.post("/api/v1/reservas", json=create_payload, headers=idem(auth_headers, key))
    assert repeated.status_code == 201
    assert repeated.json() == created.json()
    assert len(fake_parkings.assign_calls) == 1
    assert db_session.query(Reservation).count() == 1
    assert db_session.query(OutboxEvent).count() == 1


def test_reusing_key_with_another_body_is_conflict(client, auth_headers, create_payload):
    key = str(uuid4())
    assert client.post("/api/v1/reservas", json=create_payload, headers=idem(auth_headers, key)).status_code == 201
    changed = {**create_payload, "spot_id": str(uuid4())}
    response = client.post("/api/v1/reservas", json=changed, headers=idem(auth_headers, key))
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "IDEMPOTENCY_KEY_REUSED"


def test_transient_creation_stays_pending_and_same_operation_recovers(
    client, fake_parkings, auth_headers, create_payload
):
    fake_parkings.assign_results = [ParkingResult("transient"), ParkingResult("assigned", 200)]
    key = str(uuid4())
    pending = client.post("/api/v1/reservas", json=create_payload, headers=idem(auth_headers, key))
    assert pending.status_code == 202
    assert pending.headers["Retry-After"] == "2"
    reservation_id = pending.json()["reservation"]["id"]
    first_operation = fake_parkings.assign_calls[0][3]

    recovered = client.post("/api/v1/reservas", json=create_payload, headers=idem(auth_headers, key))
    assert recovered.status_code == 201
    assert recovered.json()["reservation"]["id"] == reservation_id
    assert fake_parkings.assign_calls[1][3] == first_operation


def test_definitive_rejection_is_stable(client, fake_parkings, auth_headers, create_payload):
    fake_parkings.assign_results = [ParkingResult("rejected", 409, "SPOT_UNAVAILABLE", "occupied")]
    key = str(uuid4())
    rejected = client.post("/api/v1/reservas", json=create_payload, headers=idem(auth_headers, key))
    assert rejected.status_code == 409
    assert rejected.json()["error"]["details"]["reason"] == "occupied"
    reservation_id = rejected.json()["error"]["details"]["reservation_id"]

    repeated = client.post("/api/v1/reservas", json=create_payload, headers=idem(auth_headers, key))
    assert repeated.status_code == 409
    assert repeated.json()["error"]["details"]["reservation_id"] == reservation_id
    assert len(fake_parkings.assign_calls) == 1


def test_list_get_and_ownership(client, auth_headers, other_auth_headers, create_payload):
    created = client.post("/api/v1/reservas", json=create_payload, headers=idem(auth_headers)).json()["reservation"]
    listed = client.get("/api/v1/reservas?status=confirmed", headers=auth_headers)
    assert listed.status_code == 200
    assert listed.json()["items"][0]["id"] == created["id"]
    assert listed.json()["next_cursor"] is None
    assert client.get(f"/api/v1/reservas/{created['id']}", headers=auth_headers).status_code == 200
    assert client.get(f"/api/v1/reservas/{created['id']}", headers=other_auth_headers).status_code == 404
    assert client.post(
        f"/api/v1/reservas/{created['id']}/cancelacion", headers=idem(other_auth_headers)
    ).status_code == 404


def test_cancel_is_idempotent_and_publishes_snapshot(
    client, db_session, fake_parkings, auth_headers, create_payload
):
    created = client.post("/api/v1/reservas", json=create_payload, headers=idem(auth_headers)).json()["reservation"]
    key = str(uuid4())
    route = f"/api/v1/reservas/{created['id']}/cancelacion"
    cancelled = client.post(route, headers=idem(auth_headers, key))
    assert cancelled.status_code == 200
    assert cancelled.json()["reservation"]["status"] == "cancelled"
    assert cancelled.json()["reservation"]["ever_confirmed"] is True

    repeated = client.post(route, headers=idem(auth_headers, key))
    assert repeated.status_code == 200
    assert repeated.json() == cancelled.json()
    assert len(fake_parkings.release_calls) == 1
    assert db_session.query(OutboxEvent).count() == 2


def test_cancel_pending_reservation_prevents_late_confirmation(
    client, fake_parkings, auth_headers, create_payload
):
    fake_parkings.assign_results = [ParkingResult("transient")]
    pending = client.post("/api/v1/reservas", json=create_payload, headers=idem(auth_headers)).json()["reservation"]
    cancelled = client.post(
        f"/api/v1/reservas/{pending['id']}/cancelacion", headers=idem(auth_headers)
    )
    assert cancelled.status_code == 200
    assert cancelled.json()["reservation"]["status"] == "cancelled"
    assert cancelled.json()["reservation"]["ever_confirmed"] is False


def test_headers_and_authentication_are_required(client, auth_headers, create_payload):
    assert client.post("/api/v1/reservas", json=create_payload).status_code == 401
    missing_key = client.post("/api/v1/reservas", json=create_payload, headers=auth_headers)
    assert missing_key.status_code == 400
    assert missing_key.json()["error"]["code"] == "INVALID_IDEMPOTENCY_KEY"


def test_invalid_cursor_uses_contract_error(client, auth_headers):
    response = client.get("/api/v1/reservas?cursor=%%%", headers=auth_headers)
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_CURSOR"


def test_unexpected_parking_client_error_is_transient():
    response = httpx.Response(403, json={"error": {"code": "FORBIDDEN", "details": {}}})
    assert ParkingClient._assignment_result(response).outcome == "transient"


def test_new_cancel_key_on_cancelled_is_noop(client, fake_parkings, auth_headers, create_payload):
    created = client.post("/api/v1/reservas", json=create_payload, headers=idem(auth_headers)).json()["reservation"]
    route = f"/api/v1/reservas/{created['id']}/cancelacion"
    assert client.post(route, headers=idem(auth_headers)).status_code == 200
    again = client.post(route, headers=idem(auth_headers))
    assert again.status_code == 200
    assert len(fake_parkings.release_calls) == 1

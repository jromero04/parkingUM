import uuid

from app.models import Assignment, OutboxEvent, Spot

from conftest import PARKING_ID, SPOT_ID


def assignment_payload():
    return {"parking_id": PARKING_ID, "spot_id": SPOT_ID, "operation_id": str(uuid.uuid4())}


def test_public_endpoints_require_jwt_and_expose_contract_shape(client, auth_headers):
    unauthorized = client.get("/api/v1/parkings")
    assert unauthorized.status_code == 401

    response = client.get("/api/v1/parkings", headers=auth_headers)
    assert response.status_code == 200
    assert response.json()[0]["id"] == PARKING_ID

    spots = client.get(f"/api/v1/parkings/{PARKING_ID}/plazas?availability=available", headers=auth_headers)
    assert spots.status_code == 200
    assert spots.json()[0]["availability"] == "available"


def test_assignment_is_atomic_and_idempotent(client, db_session, service_headers):
    reservation_id = str(uuid.uuid4())
    payload = assignment_payload()
    route = f"/internal/v1/asignaciones/{reservation_id}"

    created = client.put(route, json=payload, headers=service_headers)
    assert created.status_code == 201
    assert created.json()["status"] == "assigned"

    repeated = client.put(route, json=payload, headers=service_headers)
    assert repeated.status_code == 200
    assert repeated.json()["reservation_id"] == reservation_id

    conflict = client.put(
        f"/internal/v1/asignaciones/{uuid.uuid4()}",
        json=assignment_payload(),
        headers=service_headers,
    )
    assert conflict.status_code == 409
    assert conflict.json()["error"]["details"]["reason"] == "assigned"
    assert db_session.query(OutboxEvent).count() == 1


def test_internal_routes_require_the_reservations_service(client):
    response = client.put(f"/internal/v1/asignaciones/{uuid.uuid4()}", json=assignment_payload())
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "FORBIDDEN"


def test_release_is_idempotent_and_late_put_cannot_revive_assignment(client, db_session, service_headers):
    reservation_id = str(uuid.uuid4())
    route = f"/internal/v1/asignaciones/{reservation_id}"
    release_key = str(uuid.uuid4())
    released = client.delete(route, headers={**service_headers, "Idempotency-Key": release_key})
    assert released.status_code == 200
    assert released.json()["status"] == "released"

    late = client.put(route, json=assignment_payload(), headers=service_headers)
    assert late.status_code == 409
    assert late.json()["error"]["code"] == "ASSIGNMENT_CLOSED"
    assert db_session.get(Spot, SPOT_ID).assigned_reservation_id is None

    repeated = client.delete(route, headers={**service_headers, "Idempotency-Key": release_key})
    assert repeated.status_code == 200


def test_release_only_clears_its_own_assignment(client, db_session, service_headers):
    reservation_id = str(uuid.uuid4())
    route = f"/internal/v1/asignaciones/{reservation_id}"
    created = client.put(route, json=assignment_payload(), headers=service_headers)
    assert created.status_code == 201

    spot = db_session.get(Spot, SPOT_ID)
    spot.physical_occupied = True
    db_session.commit()
    released = client.delete(route, headers={**service_headers, "Idempotency-Key": str(uuid.uuid4())})
    assert released.status_code == 200
    db_session.refresh(spot)
    assert spot.assigned_reservation_id is None
    assert spot.physical_occupied is True
    assert db_session.get(Assignment, reservation_id).status == "released"

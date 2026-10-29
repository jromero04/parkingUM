from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.projection import process_event
from app.schemas import EventEnvelope

from conftest import PARKING_ID, RESERVATION_ID, SPOT_ID, parking_event, reservation_event


def project(db, event):
    process_event(db, EventEnvelope.model_validate(event))
    db.commit()


def test_metrics_requires_admin(client, user_headers):
    assert client.get("/api/v1/metricas/resumen").status_code == 401
    forbidden = client.get("/api/v1/metricas/resumen", headers=user_headers)
    assert forbidden.status_code == 403
    assert forbidden.json()["error"]["code"] == "FORBIDDEN"


def test_summary_uses_current_snapshots_and_accumulated_reservations(db_session, client, admin_headers):
    expires = datetime.now(timezone.utc) + timedelta(minutes=1)
    project(db_session, parking_event(version=2, availability="reserved", occupied=False,
                                      assigned=RESERVATION_ID, status="fresh", expires_at=expires))
    project(db_session, reservation_event(version=4, status="cancelled", ever_confirmed=True))
    response = client.get(f"/api/v1/metricas/resumen?parking_id={PARKING_ID}", headers=admin_headers)
    assert response.status_code == 200
    value = response.json()
    assert value["spots"] == {
        "total": 1, "available": 0, "reserved": 1, "occupied": 0, "unknown": 0,
        "assigned_total": 1, "physically_occupied_fresh": 0,
    }
    assert value["reservations"] == {"confirmed_current": 0, "created_total": 1, "cancelled_total": 1}
    assert value["occupancy"] == {"occupied_fresh": 0, "fresh_total": 1, "percentage": 0.0}
    assert value["consistency"] == "eventual"


def test_expired_sensor_is_unknown_and_generates_alert(db_session, client, admin_headers):
    expires = datetime.now(timezone.utc) - timedelta(seconds=1)
    project(db_session, parking_event(version=2, availability="available", occupied=False,
                                      status="fresh", expires_at=expires))
    summary = client.get("/api/v1/metricas/resumen", headers=admin_headers).json()
    assert summary["spots"]["unknown"] == 1
    assert summary["occupancy"]["percentage"] is None
    alerts = client.get("/api/v1/metricas/alertas", headers=admin_headers)
    assert alerts.status_code == 200
    assert alerts.json()["items"][0]["spot_id"] == SPOT_ID
    assert alerts.json()["items"][0]["label"] == "A-01"
    assert alerts.json()["items"][0]["code"] == "SENSOR_DATA_STALE"


def test_admin_can_list_current_spots_for_occupancy_map(db_session, client, admin_headers, user_headers):
    expires = datetime.now(timezone.utc) + timedelta(minutes=1)
    project(db_session, parking_event(version=3, availability="occupied", occupied=True,
                                      assigned=RESERVATION_ID, status="fresh", expires_at=expires))

    response = client.get("/api/v1/metricas/plazas", headers=admin_headers)
    assert response.status_code == 200
    assert response.json()[0]["label"] == "A-01"
    assert response.json()[0]["availability"] == "occupied"
    assert response.json()[0]["physical_occupied"] is True

    assert client.get("/api/v1/metricas/plazas", headers=user_headers).status_code == 403


def test_most_used_spots_report_ranks_and_filters_by_period(db_session, client, admin_headers):
    second_spot = str(uuid4())
    project(db_session, parking_event(version=1, spot_id=SPOT_ID, label="A-01"))
    project(db_session, parking_event(version=1, spot_id=second_spot, sensor_id=str(uuid4()), label="B-01"))
    recent = datetime.now(timezone.utc) - timedelta(days=2)
    project(db_session, reservation_event(version=4, status="used", reservation_id=str(uuid4()),
                                          spot_id=SPOT_ID, used_at=recent))
    project(db_session, reservation_event(version=4, status="used", reservation_id=str(uuid4()),
                                          spot_id=SPOT_ID, used_at=recent + timedelta(hours=1)))
    project(db_session, reservation_event(version=4, status="used", reservation_id=str(uuid4()),
                                          spot_id=second_spot,
                                          used_at=datetime.now(timezone.utc) - timedelta(days=40)))

    recent_report = client.get(
        "/api/v1/metricas/plazas/mas-utilizadas?periodo=30d", headers=admin_headers
    )
    assert recent_report.status_code == 200
    assert recent_report.json()["total_uses"] == 2
    assert recent_report.json()["items"][0]["label"] == "A-01"
    assert recent_report.json()["items"][0]["uses"] == 2
    assert recent_report.json()["items"][0]["percentage"] == 100.0

    historical = client.get(
        "/api/v1/metricas/plazas/mas-utilizadas?periodo=all", headers=admin_headers
    ).json()
    assert historical["total_uses"] == 3
    assert [item["label"] for item in historical["items"]] == ["A-01", "B-01"]
    assert client.get(
        "/api/v1/metricas/plazas/mas-utilizadas?limit=251", headers=admin_headers
    ).status_code == 422


def test_unknown_parking_and_invalid_cursor_use_contract_errors(db_session, client, admin_headers):
    project(db_session, parking_event())
    missing = client.get(f"/api/v1/metricas/resumen?parking_id={uuid4()}", headers=admin_headers)
    assert missing.status_code == 404
    invalid = client.get("/api/v1/metricas/alertas?cursor=%%%", headers=admin_headers)
    assert invalid.status_code == 400
    assert invalid.json()["error"]["code"] == "INVALID_CURSOR"

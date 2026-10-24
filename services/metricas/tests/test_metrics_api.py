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
    assert alerts.json()["items"][0]["code"] == "SENSOR_DATA_STALE"


def test_unknown_parking_and_invalid_cursor_use_contract_errors(db_session, client, admin_headers):
    project(db_session, parking_event())
    missing = client.get(f"/api/v1/metricas/resumen?parking_id={uuid4()}", headers=admin_headers)
    assert missing.status_code == 404
    invalid = client.get("/api/v1/metricas/alertas?cursor=%%%", headers=admin_headers)
    assert invalid.status_code == 400
    assert invalid.json()["error"]["code"] == "INVALID_CURSOR"

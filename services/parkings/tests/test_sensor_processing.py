import uuid
from datetime import datetime, timedelta, timezone

from app.models import OutboxEvent, Spot
from app.schemas import EventEnvelope
from app.sensor_processing import mark_expired_sensors, process_sensor_event

from conftest import SENSOR_ID, SPOT_ID


def envelope(sequence: int, occupied: bool, event_id: str | None = None, observed_at=None):
    now = observed_at or datetime.now(timezone.utc)
    return EventEnvelope.model_validate(
        {
            "event_id": event_id or str(uuid.uuid4()),
            "event_type": "sensor.reported.v1",
            "schema_version": 1,
            "occurred_at": now.isoformat(),
            "producer": "sensor-simulator",
            "correlation_id": str(uuid.uuid4()),
            "data": {
                "sensor_id": SENSOR_ID,
                "spot_id": SPOT_ID,
                "sequence": sequence,
                "observed_at": now.isoformat(),
                "physical_occupied": occupied,
            },
        }
    )


def test_sensor_event_updates_spot_and_duplicate_has_no_second_effect(db_session):
    event = envelope(2, True)
    assert process_sensor_event(db_session, event).status == "accepted"
    db_session.commit()
    spot = db_session.get(Spot, SPOT_ID)
    first_version = spot.version
    assert spot.physical_occupied is True

    assert process_sensor_event(db_session, event).status == "duplicate"
    db_session.commit()
    db_session.refresh(spot)
    assert spot.version == first_version
    assert db_session.query(OutboxEvent).count() == 1


def test_old_sensor_report_is_recorded_but_does_not_rejuvenate_spot(db_session):
    spot = db_session.get(Spot, SPOT_ID)
    original_expiry = spot.sensor_expires_at
    assert process_sensor_event(db_session, envelope(1, True)).status == "discarded"
    db_session.commit()
    db_session.refresh(spot)
    assert spot.physical_occupied is False
    assert spot.sensor_expires_at == original_expiry


def test_expiration_marks_sensor_stale_without_erasing_physical_state(db_session):
    spot = db_session.get(Spot, SPOT_ID)
    spot.physical_occupied = True
    spot.sensor_expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    db_session.commit()

    assert mark_expired_sensors(db_session) == 1
    db_session.commit()
    db_session.refresh(spot)
    assert spot.sensor_status == "stale"
    assert spot.physical_occupied is True
    assert db_session.query(OutboxEvent).count() == 1


def test_event_contract_ignores_compatible_unknown_fields():
    now = datetime.now(timezone.utc)
    value = EventEnvelope.model_validate(
        {
            "event_id": str(uuid.uuid4()),
            "event_type": "sensor.reported.v1",
            "schema_version": 1,
            "occurred_at": now.isoformat(),
            "producer": "sensor-simulator",
            "correlation_id": str(uuid.uuid4()),
            "future_envelope_field": "ignored",
            "data": {
                "sensor_id": SENSOR_ID,
                "spot_id": SPOT_ID,
                "sequence": 2,
                "observed_at": now.isoformat(),
                "physical_occupied": False,
                "future_data_field": "ignored",
            },
        }
    )
    assert not hasattr(value, "future_envelope_field")
    assert not hasattr(value.data, "future_data_field")

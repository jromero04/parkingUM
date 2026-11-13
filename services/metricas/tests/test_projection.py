from app.models import ProcessedEvent, ReservationProjection, SpotProjection, SpotUsageRecord
from app.projection import process_event
from app.schemas import EventEnvelope

from conftest import RESERVATION_ID, SPOT_ID, parking_event, reservation_event


def apply(db, value):
    result = process_event(db, EventEnvelope.model_validate(value))
    db.commit()
    return result


def test_parking_projection_is_idempotent_and_keeps_highest_version(db_session):
    event = parking_event(version=3, availability="available", occupied=False)
    assert apply(db_session, event).status == "applied"
    assert apply(db_session, event).status == "duplicate"
    assert apply(db_session, parking_event(version=2, availability="occupied", occupied=True)).status == "discarded"
    value = db_session.get(SpotProjection, SPOT_ID)
    assert value.version == 3
    assert value.availability == "available"
    assert db_session.query(ProcessedEvent).count() == 2


def test_cancelled_snapshot_arriving_first_suppresses_older_created(db_session):
    assert apply(db_session, reservation_event(version=4, status="cancelled")).status == "applied"
    assert apply(db_session, reservation_event(version=2, status="confirmed")).status == "discarded"
    value = db_session.get(ReservationProjection, RESERVATION_ID)
    assert value.status == "cancelled"
    assert value.ever_confirmed is True
    assert value.version == 4


def test_compatible_unknown_fields_are_ignored(db_session):
    event = parking_event()
    event["future"] = "ignored"
    event["data"]["spot"]["future"] = "ignored"
    assert apply(db_session, event).status == "applied"


def test_used_reservation_creates_one_idempotent_usage_record(db_session):
    event = reservation_event(version=4, status="used")
    assert apply(db_session, event).status == "applied"
    assert apply(db_session, event).status == "duplicate"
    usage = db_session.get(SpotUsageRecord, RESERVATION_ID)
    assert usage.spot_id == SPOT_ID
    assert db_session.query(SpotUsageRecord).count() == 1

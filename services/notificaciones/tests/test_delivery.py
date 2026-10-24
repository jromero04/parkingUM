from app.delivery import process_event
from app.models import Delivery, ProcessedEvent, ReservationState
from app.recipient_client import PermanentRecipientError
from conftest import FakeRecipients, RESERVATION_ID, event


def apply(db, value, recipients):
    result = process_event(db, value, recipients)
    db.commit()
    return result


def test_delivery_and_duplicate_are_persistent(db_session):
    recipients = FakeRecipients()
    value = event()
    first = apply(db_session, value, recipients)
    repeated = apply(db_session, value, recipients)
    assert first.status == "delivered" and first.template == "reservation_confirmed"
    assert repeated.status == "duplicate" and repeated.delivery_id == first.delivery_id
    assert len(recipients.calls) == 1 and db_session.query(Delivery).count() == 1
    assert db_session.query(ProcessedEvent).count() == 1


def test_newer_cancellation_suppresses_old_confirmation(db_session):
    recipients = FakeRecipients()
    cancelled = apply(db_session, event(version=4, status="cancelled"), recipients)
    old = apply(db_session, event(version=2, status="confirmed"), recipients)
    assert cancelled.template == "reservation_cancelled" and old.status == "suppressed"
    assert len(recipients.calls) == 1
    state = db_session.get(ReservationState, RESERVATION_ID)
    assert state.highest_version == 4 and state.status == "cancelled"


def test_never_confirmed_cancellation_uses_request_template(db_session):
    result = apply(db_session, event(version=3, status="cancelled", ever=False), FakeRecipients())
    assert result.status == "delivered" and result.template == "request_cancelled"


def test_unknown_compatible_fields_are_ignored(db_session):
    value = event()
    raw = value.model_dump(mode="json")
    raw["future"] = "ignored"
    raw["data"]["future"] = "ignored"
    from app.schemas import EventEnvelope
    assert apply(db_session, EventEnvelope.model_validate(raw), FakeRecipients()).status == "delivered"


def test_permanent_recipient_failure_does_not_record_delivery(db_session):
    class MissingRecipient:
        def get(self, user_id, correlation_id):
            raise PermanentRecipientError("missing")
    import pytest
    with pytest.raises(PermanentRecipientError):
        process_event(db_session, event(), MissingRecipient())
    db_session.rollback()
    assert db_session.query(Delivery).count() == 0
    assert db_session.query(ProcessedEvent).count() == 0

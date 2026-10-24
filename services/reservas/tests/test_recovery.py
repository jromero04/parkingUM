from datetime import datetime, timezone
from uuid import uuid4

from app.domain import attempt_pending
from app.models import IdempotencyRecord, OutboxEvent, Reservation
from app.parking_client import ParkingResult

from conftest import PARKING_ID, SPOT_ID, USER_ID, FakeParkingClient


def pending_reservation(db_session, status="pending"):
    now = datetime.now(timezone.utc)
    value = Reservation(
        user_id=USER_ID, parking_id=PARKING_ID, spot_id=SPOT_ID,
        operation_id=str(uuid4()), cancellation_operation_id=str(uuid4()) if status == "cancel_pending" else None,
        status=status, correlation_id=str(uuid4()), created_at=now, updated_at=now, next_attempt_at=now,
    )
    db_session.add(value)
    db_session.flush()
    db_session.add(IdempotencyRecord(
        user_id=USER_ID, idempotency_key=str(uuid4()), method="POST",
        path="/api/v1/reservas" if status == "pending" else f"/api/v1/reservas/{value.id}/cancelacion",
        request_hash="hash", reservation_id=value.id,
    ))
    db_session.commit()
    return value


def test_recovery_confirms_pending_with_same_operation(db_session):
    value = pending_reservation(db_session)
    client = FakeParkingClient()
    client.assign_results = [ParkingResult("transient"), ParkingResult("assigned", 200)]
    first = attempt_pending(db_session, value.id, client)
    assert first.status == "pending"
    second = attempt_pending(db_session, value.id, client)
    assert second.status == "confirmed"
    assert client.assign_calls[0][3] == client.assign_calls[1][3]
    assert db_session.query(OutboxEvent).count() == 1


def test_recovery_finishes_cancel_pending(db_session):
    value = pending_reservation(db_session, "cancel_pending")
    client = FakeParkingClient()
    recovered = attempt_pending(db_session, value.id, client)
    assert recovered.status == "cancelled"
    assert recovered.ever_confirmed is False
    assert db_session.query(OutboxEvent).count() == 1

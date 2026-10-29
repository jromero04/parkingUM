from datetime import datetime, timezone
from uuid import uuid4

from app.models import OutboxEvent, Reservation
from app.parking_processing import process_parking_event
from app.schemas import ParkingEventEnvelope

from conftest import PARKING_ID, SPOT_ID, USER_ID


def event(reservation_id: str, occupied: bool) -> ParkingEventEnvelope:
    now = datetime.now(timezone.utc)
    return ParkingEventEnvelope.model_validate({
        "event_id": str(uuid4()),
        "event_type": "parking.availability_changed.v1",
        "schema_version": 1,
        "occurred_at": now.isoformat(),
        "producer": "parkings",
        "correlation_id": str(uuid4()),
        "data": {
            "reason": "sensor_state_changed",
            "spot": {
                "id": SPOT_ID,
                "assigned_reservation_id": reservation_id,
                "physical_occupied": occupied,
            },
        },
    })


def confirmed_reservation(db_session) -> Reservation:
    now = datetime.now(timezone.utc)
    value = Reservation(
        user_id=USER_ID,
        parking_id=PARKING_ID,
        spot_id=SPOT_ID,
        operation_id=str(uuid4()),
        status="confirmed",
        ever_confirmed=True,
        confirmed_at=now,
        correlation_id=str(uuid4()),
        next_attempt_at=now,
    )
    db_session.add(value)
    db_session.commit()
    return value


def test_sensor_transitions_reservation_from_confirmed_to_occupied_to_used(
    db_session, fake_parkings
):
    value = confirmed_reservation(db_session)

    occupied_event = event(value.id, True)
    occupied = process_parking_event(db_session, occupied_event, fake_parkings)
    db_session.commit()
    assert occupied.reservation_status == "occupied"
    assert value.occupied_at is not None
    assert len(fake_parkings.release_calls) == 0

    free_event = event(value.id, False)
    used = process_parking_event(db_session, free_event, fake_parkings)
    db_session.commit()
    assert used.reservation_status == "used"
    assert value.used_at is not None
    assert fake_parkings.release_calls[0][0] == value.id
    assert fake_parkings.release_calls[0][1] == str(free_event.event_id)
    assert db_session.query(OutboxEvent).count() == 2

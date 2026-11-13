from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Reservation
from app.outbox import add_reservation_event
from app.parking_client import ParkingClient
from app.schemas import ParkingEventEnvelope


@dataclass(frozen=True)
class ParkingProcessResult:
    status: str
    reservation_id: str | None = None
    reservation_status: str | None = None


def as_utc(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def process_parking_event(
    session: Session,
    envelope: ParkingEventEnvelope,
    parking_client: ParkingClient,
) -> ParkingProcessResult:
    spot = envelope.data.spot
    if spot.assigned_reservation_id is None:
        return ParkingProcessResult("ignored")
    reservation_id = str(spot.assigned_reservation_id)
    value = session.scalar(select(Reservation).where(
        Reservation.id == reservation_id,
        Reservation.spot_id == str(spot.id),
    ).with_for_update())
    if value is None:
        return ParkingProcessResult("ignored", reservation_id)

    now = as_utc(envelope.occurred_at)
    if spot.physical_occupied is True and value.status == "confirmed":
        value.status = "occupied"
        value.occupied_at = now
        value.updated_at = now
        value.version += 1
        value.correlation_id = str(envelope.correlation_id)
        add_reservation_event(session, value, "reservation.occupied.v1", value.correlation_id)
        return ParkingProcessResult("applied", value.id, value.status)

    if spot.physical_occupied is False and value.status == "occupied":
        result = parking_client.release(
            value.id, str(envelope.event_id), str(envelope.correlation_id)
        )
        if result.outcome != "released":
            raise RuntimeError("No se pudo liberar la plaza al finalizar su uso")
        value.status = "used"
        value.used_at = now
        value.updated_at = now
        value.version += 1
        value.correlation_id = str(envelope.correlation_id)
        add_reservation_event(session, value, "reservation.used.v1", value.correlation_id)
        return ParkingProcessResult("applied", value.id, value.status)

    return ParkingProcessResult("ignored", value.id, value.status)

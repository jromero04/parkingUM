import json
import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models import OutboxEvent, Reservation


def rfc3339(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def reservation_snapshot(value: Reservation) -> dict:
    return {
        "id": value.id,
        "user_id": value.user_id,
        "parking_id": value.parking_id,
        "spot_id": value.spot_id,
        "status": value.status,
        "ever_confirmed": value.ever_confirmed,
        "created_at": rfc3339(value.created_at),
        "updated_at": rfc3339(value.updated_at),
        "confirmed_at": rfc3339(value.confirmed_at),
        "occupied_at": rfc3339(value.occupied_at),
        "used_at": rfc3339(value.used_at),
        "cancelled_at": rfc3339(value.cancelled_at),
        "failure_code": value.failure_code,
        "version": value.version,
    }


def add_reservation_event(
    session: Session,
    reservation: Reservation,
    event_type: str,
    correlation_id: str,
) -> None:
    now = datetime.now(timezone.utc)
    event_id = str(uuid.uuid4())
    envelope = {
        "event_id": event_id,
        "event_type": event_type,
        "schema_version": 1,
        "occurred_at": now.isoformat(),
        "producer": "reservas",
        "correlation_id": correlation_id,
        "data": {"reservation": reservation_snapshot(reservation)},
    }
    session.add(OutboxEvent(
        event_id=event_id,
        event_type=event_type,
        correlation_id=correlation_id,
        payload=json.dumps(envelope, separators=(",", ":")),
        created_at=now,
    ))

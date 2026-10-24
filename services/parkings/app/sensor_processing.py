import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import ProcessedEvent, Spot
from app.outbox import add_spot_event, availability
from app.schemas import EventEnvelope


CONSUMER_NAME = "parkings-sensors"


class UnknownSensorError(ValueError):
    pass


@dataclass(frozen=True)
class SensorProcessResult:
    status: str
    event_type: str | None = None


def as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def process_sensor_event(session: Session, envelope: EventEnvelope, now: datetime | None = None) -> SensorProcessResult:
    now = as_utc(now or datetime.now(timezone.utc))
    event_id = str(envelope.event_id)
    if session.get(ProcessedEvent, (CONSUMER_NAME, event_id)) is not None:
        return SensorProcessResult("duplicate")

    data = envelope.data
    spot = session.scalar(select(Spot).where(Spot.sensor_id == str(data.sensor_id)).with_for_update())
    if spot is None or spot.id != str(data.spot_id):
        raise UnknownSensorError("sensor_id y spot_id no coinciden con el seed")

    observed_at = as_utc(data.observed_at)
    if observed_at > now + timedelta(seconds=2):
        raise ValueError("observed_at excede la tolerancia futura")
    effective_observed_at = min(observed_at, now)
    expires_at = effective_observed_at + timedelta(seconds=get_settings().sensor_fresh_seconds)
    current_report = as_utc(spot.last_report_at) if spot.last_report_at else None
    stale_or_old = (
        expires_at <= now
        or (spot.last_sequence is not None and data.sequence <= spot.last_sequence)
        or (current_report is not None and observed_at < current_report)
    )
    session.add(ProcessedEvent(consumer_name=CONSUMER_NAME, event_id=event_id, processed_at=now))
    if stale_or_old:
        return SensorProcessResult("discarded")

    was_fresh = availability(spot, now) != "unknown"
    physical_changed = spot.physical_occupied != data.physical_occupied
    spot.physical_occupied = data.physical_occupied
    spot.sensor_status = "fresh"
    spot.last_sequence = data.sequence
    spot.last_report_at = observed_at
    spot.sensor_expires_at = expires_at
    spot.version += 1
    spot.updated_at = now
    if not was_fresh:
        event_type = "parking.sensor_recovered.v1"
        reason = "fresh_report_received"
    elif physical_changed:
        event_type = "parking.availability_changed.v1"
        reason = "sensor_state_changed"
    else:
        event_type = "parking.sensor_refreshed.v1"
        reason = "heartbeat_received"
    add_spot_event(session, spot, event_type, reason, str(envelope.correlation_id))
    return SensorProcessResult("accepted", event_type)


def mark_expired_sensors(session: Session, now: datetime | None = None) -> int:
    now = as_utc(now or datetime.now(timezone.utc))
    spots = session.scalars(
        select(Spot)
        .where(Spot.sensor_status == "fresh", Spot.sensor_expires_at.is_not(None), Spot.sensor_expires_at <= now)
        .with_for_update(skip_locked=True)
    ).all()
    for spot in spots:
        spot.sensor_status = "stale"
        spot.version += 1
        spot.updated_at = now
        add_spot_event(session, spot, "parking.sensor_stale.v1", "report_timeout", str(uuid.uuid4()))
    return len(spots)

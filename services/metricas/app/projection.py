from dataclasses import dataclass
from datetime import datetime, timezone

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import ProcessedEvent, ReservationProjection, SpotProjection, SpotUsageRecord
from app.schemas import EventEnvelope, ParkingData, ReservationData


CONSUMER_NAME = "metricas"
PARKING_EVENTS = {
    "parking.spot_initialized.v1", "parking.availability_changed.v1", "parking.sensor_stale.v1",
    "parking.sensor_recovered.v1", "parking.sensor_refreshed.v1",
}
RESERVATION_EVENTS = {
    "reservation.created.v1", "reservation.occupied.v1", "reservation.used.v1", "reservation.cancelled.v1",
}


class UnsupportedEventError(ValueError):
    pass


@dataclass(frozen=True)
class ProjectionResult:
    status: str
    entity_id: str | None = None
    version: int | None = None


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def process_event(session: Session, envelope: EventEnvelope) -> ProjectionResult:
    event_id = str(envelope.event_id)
    if session.get(ProcessedEvent, (CONSUMER_NAME, event_id)) is not None:
        return ProjectionResult("duplicate")
    if envelope.event_type in PARKING_EVENTS:
        result = apply_spot(session, envelope)
    elif envelope.event_type in RESERVATION_EVENTS:
        result = apply_reservation(session, envelope)
    else:
        raise UnsupportedEventError(envelope.event_type)
    session.add(ProcessedEvent(consumer_name=CONSUMER_NAME, event_id=event_id, processed_at=now_utc()))
    return result


def apply_spot(session: Session, envelope: EventEnvelope) -> ProjectionResult:
    snapshot = ParkingData.model_validate(envelope.data).spot
    entity_id = str(snapshot.id)
    value = session.scalar(select(SpotProjection).where(SpotProjection.id == entity_id).with_for_update())
    if value is not None and value.version >= snapshot.version:
        return ProjectionResult("discarded", entity_id, snapshot.version)
    projected_at = now_utc()
    if value is None:
        value = SpotProjection(id=entity_id, initialized_at=envelope.occurred_at)
        session.add(value)
    value.parking_id = str(snapshot.parking_id)
    value.sensor_id = str(snapshot.sensor_id)
    value.label = snapshot.label
    value.physical_occupied = snapshot.physical_occupied
    value.assigned_reservation_id = str(snapshot.assigned_reservation_id) if snapshot.assigned_reservation_id else None
    value.sensor_status = snapshot.sensor_status
    value.last_report_at = snapshot.last_report_at
    value.sensor_expires_at = snapshot.sensor_expires_at
    value.availability = snapshot.availability
    value.version = snapshot.version
    value.source_updated_at = snapshot.updated_at
    value.projected_at = projected_at
    return ProjectionResult("applied", entity_id, snapshot.version)


def apply_reservation(session: Session, envelope: EventEnvelope) -> ProjectionResult:
    snapshot = ReservationData.model_validate(envelope.data).reservation
    entity_id = str(snapshot.id)
    value = session.scalar(select(ReservationProjection).where(
        ReservationProjection.id == entity_id
    ).with_for_update())
    if value is not None and value.version >= snapshot.version:
        return ProjectionResult("discarded", entity_id, snapshot.version)
    if value is None:
        value = ReservationProjection(id=entity_id)
        session.add(value)
    value.user_id = str(snapshot.user_id)
    value.parking_id = str(snapshot.parking_id)
    value.spot_id = str(snapshot.spot_id)
    value.status = snapshot.status
    value.ever_confirmed = snapshot.ever_confirmed
    value.created_at = snapshot.created_at
    value.source_updated_at = snapshot.updated_at
    value.confirmed_at = snapshot.confirmed_at
    value.cancelled_at = snapshot.cancelled_at
    value.failure_code = snapshot.failure_code
    value.version = snapshot.version
    value.projected_at = now_utc()
    if snapshot.status == "used" and session.get(SpotUsageRecord, entity_id) is None:
        session.add(SpotUsageRecord(
            reservation_id=entity_id,
            event_id=str(envelope.event_id),
            parking_id=str(snapshot.parking_id),
            spot_id=str(snapshot.spot_id),
            used_at=snapshot.used_at or snapshot.updated_at,
            projected_at=now_utc(),
        ))
    return ProjectionResult("applied", entity_id, snapshot.version)


PERMANENT_EVENT_ERRORS = (ValidationError, UnsupportedEventError, ValueError)

import json
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.logging_config import log_event
from app.models import IdempotencyRecord, Reservation
from app.outbox import add_reservation_event
from app.parking_client import ParkingClient, ParkingResult
from app.schemas import ReservationRead, ReservationResponse


logger = logging.getLogger("reservas.domain")


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def retry_delay(attempt: int) -> int:
    if attempt <= 1:
        return 5
    if attempt == 2:
        return 15
    return 60


def creation_error(value: Reservation) -> tuple[int, str, str, dict]:
    details = {"reservation_id": value.id}
    if value.failure_reason:
        details["reason"] = value.failure_reason
    if value.failure_code == "RESOURCE_NOT_FOUND":
        return 404, "RESOURCE_NOT_FOUND", "El estacionamiento o la plaza no existe.", details
    if value.failure_code == "ASSIGNMENT_CLOSED":
        return 409, "ASSIGNMENT_CLOSED", "La asignacion ya fue cerrada.", details
    return 409, "SPOT_UNAVAILABLE", "La plaza no esta disponible.", details


def success_payload(value: Reservation) -> str:
    body = ReservationResponse(reservation=ReservationRead.model_validate(value)).model_dump(mode="json")
    return json.dumps(body, separators=(",", ":"))


def error_payload(value: Reservation) -> str:
    status, code, message, details = creation_error(value)
    return json.dumps({"status": status, "code": code, "message": message, "details": details}, separators=(",", ":"))


def creation_record(session: Session, reservation_id: str) -> IdempotencyRecord | None:
    return session.scalar(select(IdempotencyRecord).where(
        IdempotencyRecord.reservation_id == reservation_id,
        IdempotencyRecord.path == "/api/v1/reservas",
    ))


def cancellation_records(session: Session, reservation_id: str) -> list[IdempotencyRecord]:
    return list(session.scalars(select(IdempotencyRecord).where(
        IdempotencyRecord.reservation_id == reservation_id,
        IdempotencyRecord.path != "/api/v1/reservas",
        IdempotencyRecord.response_status.is_(None),
    )).all())


def schedule_retry(value: Reservation, now: datetime) -> None:
    value.attempt_count += 1
    value.last_attempt_at = now
    value.next_attempt_at = now + timedelta(seconds=retry_delay(value.attempt_count))
    value.lease_owner = None
    value.lease_until = None


def attempt_assignment(
    session: Session,
    reservation_id: str,
    parking_client: ParkingClient,
) -> Reservation:
    value = session.get(Reservation, reservation_id)
    if value is None:
        raise LookupError(reservation_id)
    if value.status != "pending":
        return value
    args = (value.id, value.parking_id, value.spot_id, value.operation_id, value.correlation_id)
    session.rollback()
    result = parking_client.assign(*args)
    value = session.scalar(select(Reservation).where(Reservation.id == reservation_id).with_for_update())
    if value is None:
        raise LookupError(reservation_id)
    if value.status != "pending":
        session.rollback()
        return value
    now = utc_now()
    value.attempt_count += 1
    value.last_attempt_at = now
    value.lease_owner = None
    value.lease_until = None
    if result.outcome == "transient":
        value.next_attempt_at = now + timedelta(seconds=retry_delay(value.attempt_count))
        session.commit()
        log_event(logger, "reservation_pending", "retry", level=logging.WARNING,
                  correlation_id=value.correlation_id, reservation_id=value.id, attempt=value.attempt_count)
        return value
    if result.outcome == "assigned":
        value.status = "confirmed"
        value.ever_confirmed = True
        value.confirmed_at = now
        value.failure_code = None
        value.failure_reason = None
        value.version += 1
        value.updated_at = now
        add_reservation_event(session, value, "reservation.created.v1", value.correlation_id)
        record = creation_record(session, value.id)
        if record is not None:
            record.response_status = 201
            record.response_payload = success_payload(value)
        session.commit()
        log_event(logger, "reservation_confirmed", "success", correlation_id=value.correlation_id,
                  reservation_id=value.id, spot_id=value.spot_id, operation_id=value.operation_id,
                  entity_version=value.version)
        return value
    value.status = "rejected"
    value.failure_code = result.error_code or "SPOT_UNAVAILABLE"
    value.failure_reason = result.reason
    value.version += 1
    value.updated_at = now
    record = creation_record(session, value.id)
    if record is not None:
        record.response_status = creation_error(value)[0]
        record.response_payload = error_payload(value)
    session.commit()
    log_event(logger, "reservation_pending", "rejected", level=logging.WARNING,
              correlation_id=value.correlation_id, reservation_id=value.id, spot_id=value.spot_id,
              operation_id=value.operation_id, error_code=value.failure_code, reason=value.failure_reason)
    return value


def attempt_cancellation(
    session: Session,
    reservation_id: str,
    parking_client: ParkingClient,
) -> Reservation:
    value = session.get(Reservation, reservation_id)
    if value is None:
        raise LookupError(reservation_id)
    if value.status != "cancel_pending":
        return value
    args = (value.id, value.cancellation_operation_id, value.correlation_id)
    session.rollback()
    result = parking_client.release(*args)
    value = session.scalar(select(Reservation).where(Reservation.id == reservation_id).with_for_update())
    if value is None:
        raise LookupError(reservation_id)
    if value.status != "cancel_pending":
        session.rollback()
        return value
    now = utc_now()
    value.attempt_count += 1
    value.last_attempt_at = now
    value.lease_owner = None
    value.lease_until = None
    if result.outcome != "released":
        value.next_attempt_at = now + timedelta(seconds=retry_delay(value.attempt_count))
        session.commit()
        log_event(logger, "recovery_attempted", "retry", level=logging.WARNING,
                  correlation_id=value.correlation_id, reservation_id=value.id, attempt=value.attempt_count)
        return value
    value.status = "cancelled"
    value.cancelled_at = now
    value.failure_code = None
    value.failure_reason = None
    value.version += 1
    value.updated_at = now
    add_reservation_event(session, value, "reservation.cancelled.v1", value.correlation_id)
    for record in cancellation_records(session, value.id):
        record.response_status = 200
        record.response_payload = success_payload(value)
    session.commit()
    log_event(logger, "reservation_cancelled", "success", correlation_id=value.correlation_id,
              reservation_id=value.id, spot_id=value.spot_id,
              operation_id=value.cancellation_operation_id, entity_version=value.version)
    return value


def attempt_pending(session: Session, reservation_id: str, parking_client: ParkingClient) -> Reservation:
    value = session.get(Reservation, reservation_id)
    if value is None:
        raise LookupError(reservation_id)
    if value.status == "pending":
        return attempt_assignment(session, reservation_id, parking_client)
    if value.status == "cancel_pending":
        return attempt_cancellation(session, reservation_id, parking_client)
    return value

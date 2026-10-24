import base64
import binascii
import hashlib
import json
import uuid
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, Header, Query, Request, Response, status
from fastapi.responses import JSONResponse
from sqlalchemy import or_, select, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.database import get_db
from app.domain import attempt_cancellation, attempt_assignment, creation_error, success_payload
from app.errors import ApiError
from app.models import IdempotencyRecord, Reservation
from app.outbox import reservation_snapshot
from app.parking_client import ParkingClient, get_parking_client
from app.schemas import ReservationCollection, ReservationCreate, ReservationRead, ReservationResponse, ReservationStatus
from app.security import authenticated_claims


public_router = APIRouter(prefix="/api/v1/reservas", tags=["reservas"])
health_router = APIRouter(tags=["health"])


def parse_idempotency_key(value: str | None) -> str:
    try:
        return str(uuid.UUID(value)) if value else ""
    except ValueError:
        return ""


def lock_key(session: Session, user_id: str, key: str) -> None:
    if session.bind is not None and session.bind.dialect.name == "postgresql":
        session.execute(text("SELECT pg_advisory_xact_lock(hashtext(:value))"), {"value": f"{user_id}:{key}"})


def request_hash(payload: dict) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def reservation_response(value: Reservation, status_code: int, pending: bool = False) -> JSONResponse:
    body = ReservationResponse(reservation=ReservationRead.model_validate(value)).model_dump(mode="json")
    headers = {"Location": f"/api/v1/reservas/{value.id}"}
    if pending:
        headers["Retry-After"] = "2"
    return JSONResponse(status_code=status_code, content=body, headers=headers)


def replay(record: IdempotencyRecord, value: Reservation) -> JSONResponse | None:
    if record.response_status is None:
        return None
    payload = json.loads(record.response_payload or "{}")
    if record.response_status >= 400:
        raise ApiError(record.response_status, payload["code"], payload["message"], payload["details"])
    return JSONResponse(
        status_code=record.response_status,
        content=payload,
        headers={"Location": f"/api/v1/reservas/{value.id}"},
    )


def raise_creation_error(value: Reservation) -> None:
    status_code, code, message, details = creation_error(value)
    raise ApiError(status_code, code, message, details)


@public_router.post("", response_model=ReservationResponse)
def create_reservation(
    payload: ReservationCreate,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    claims: Annotated[dict, Depends(authenticated_claims)],
    parking_client: Annotated[ParkingClient, Depends(get_parking_client)],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> JSONResponse:
    key = parse_idempotency_key(idempotency_key)
    if not key:
        raise ApiError(400, "INVALID_IDEMPOTENCY_KEY", "Idempotency-Key debe ser un UUID.")
    user_id = claims["sub"]
    normalized = {"parking_id": str(payload.parking_id), "spot_id": str(payload.spot_id)}
    body_hash = request_hash(normalized)
    lock_key(db, user_id, key)
    record = db.get(IdempotencyRecord, (user_id, key))
    if record is not None:
        if (record.method, record.path, record.request_hash) != ("POST", "/api/v1/reservas", body_hash):
            raise ApiError(409, "IDEMPOTENCY_KEY_REUSED", "La clave ya fue usada con otra operacion.")
        value = db.get(Reservation, record.reservation_id)
        stored = replay(record, value)
        if stored is not None:
            return stored
        value = attempt_assignment(db, value.id, parking_client)
    else:
        now = datetime.now(timezone.utc)
        value = Reservation(
            user_id=user_id,
            parking_id=normalized["parking_id"],
            spot_id=normalized["spot_id"],
            operation_id=str(uuid.uuid4()),
            status="pending",
            correlation_id=request.state.correlation_id,
            created_at=now,
            updated_at=now,
            next_attempt_at=now,
        )
        db.add(value)
        db.flush()
        db.add(IdempotencyRecord(
            user_id=user_id,
            idempotency_key=key,
            method="POST",
            path="/api/v1/reservas",
            request_hash=body_hash,
            reservation_id=value.id,
        ))
        db.commit()
        value = attempt_assignment(db, value.id, parking_client)
    if value.status == "confirmed":
        return reservation_response(value, status.HTTP_201_CREATED)
    if value.status == "rejected":
        raise_creation_error(value)
    return reservation_response(value, status.HTTP_202_ACCEPTED, pending=True)


def encode_cursor(value: Reservation) -> str:
    raw = f"{value.created_at.isoformat()}|{value.id}".encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("ascii")


def decode_cursor(value: str) -> tuple[datetime, str]:
    try:
        decoded = base64.urlsafe_b64decode(value.encode("ascii")).decode("utf-8")
        timestamp, reservation_id = decoded.rsplit("|", 1)
        return datetime.fromisoformat(timestamp), str(uuid.UUID(reservation_id))
    except (binascii.Error, ValueError, UnicodeError):
        raise ApiError(400, "INVALID_CURSOR", "El cursor no es valido.") from None


@public_router.get("", response_model=ReservationCollection)
def list_reservations(
    db: Annotated[Session, Depends(get_db)],
    claims: Annotated[dict, Depends(authenticated_claims)],
    reservation_status: Annotated[ReservationStatus | None, Query(alias="status")] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    cursor: str | None = None,
) -> ReservationCollection:
    query = select(Reservation).where(Reservation.user_id == claims["sub"])
    if reservation_status is not None:
        query = query.where(Reservation.status == reservation_status)
    if cursor:
        created_at, reservation_id = decode_cursor(cursor)
        query = query.where(or_(
            Reservation.created_at > created_at,
            (Reservation.created_at == created_at) & (Reservation.id > reservation_id),
        ))
    values = list(db.scalars(query.order_by(Reservation.created_at, Reservation.id).limit(limit + 1)).all())
    next_cursor = encode_cursor(values[limit - 1]) if len(values) > limit else None
    return ReservationCollection(
        items=[ReservationRead.model_validate(value) for value in values[:limit]],
        next_cursor=next_cursor,
    )


def owned_reservation(
    db: Session,
    reservation_id: uuid.UUID,
    user_id: str,
    *,
    for_update: bool = False,
) -> Reservation:
    query = select(Reservation).where(
        Reservation.id == str(reservation_id), Reservation.user_id == user_id
    )
    if for_update:
        query = query.with_for_update()
    value = db.scalar(query)
    if value is None:
        raise ApiError(404, "RESOURCE_NOT_FOUND", "La reserva no existe.")
    return value


@public_router.get("/{reservation_id}", response_model=ReservationRead)
def get_reservation(
    reservation_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
    claims: Annotated[dict, Depends(authenticated_claims)],
) -> ReservationRead:
    return ReservationRead.model_validate(owned_reservation(db, reservation_id, claims["sub"]))


@public_router.post("/{reservation_id}/cancelacion", response_model=ReservationResponse)
def cancel_reservation(
    reservation_id: uuid.UUID,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    claims: Annotated[dict, Depends(authenticated_claims)],
    parking_client: Annotated[ParkingClient, Depends(get_parking_client)],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> JSONResponse:
    key = parse_idempotency_key(idempotency_key)
    if not key:
        raise ApiError(400, "INVALID_IDEMPOTENCY_KEY", "Idempotency-Key debe ser un UUID.")
    user_id = claims["sub"]
    path = f"/api/v1/reservas/{reservation_id}/cancelacion"
    body_hash = request_hash({})
    lock_key(db, user_id, key)
    value = owned_reservation(db, reservation_id, user_id, for_update=True)
    record = db.get(IdempotencyRecord, (user_id, key))
    if record is not None:
        if (record.method, record.path, record.request_hash) != ("POST", path, body_hash):
            raise ApiError(409, "IDEMPOTENCY_KEY_REUSED", "La clave ya fue usada con otra operacion.")
        stored = replay(record, value)
        if stored is not None:
            return stored
    else:
        record = IdempotencyRecord(
            user_id=user_id,
            idempotency_key=key,
            method="POST",
            path=path,
            request_hash=body_hash,
            reservation_id=value.id,
        )
        db.add(record)
        if value.status == "rejected":
            details = {"reservation_id": value.id}
            record.response_status = 409
            record.response_payload = json.dumps({
                "status": 409, "code": "RESERVATION_TERMINAL",
                "message": "La reserva esta en un estado terminal.", "details": details,
            })
            db.commit()
            raise ApiError(409, "RESERVATION_TERMINAL", "La reserva esta en un estado terminal.", details)
        if value.status == "cancelled":
            record.response_status = 200
            record.response_payload = success_payload(value)
            db.commit()
            return reservation_response(value, status.HTTP_200_OK)
        now = datetime.now(timezone.utc)
        if value.status != "cancel_pending":
            value.status = "cancel_pending"
            value.version += 1
            value.updated_at = now
            value.attempt_count = 0
        if value.cancellation_operation_id is None:
            value.cancellation_operation_id = key
        value.correlation_id = request.state.correlation_id
        value.next_attempt_at = now
        db.commit()
    value = attempt_cancellation(db, value.id, parking_client)
    if value.status == "cancelled":
        return reservation_response(value, status.HTTP_200_OK)
    return reservation_response(value, status.HTTP_202_ACCEPTED, pending=True)


@health_router.get("/health/live")
def live() -> dict[str, str]:
    return {"status": "live"}


@health_router.get("/health/ready")
def ready(db: Annotated[Session, Depends(get_db)]) -> dict[str, str]:
    try:
        db.execute(text("SELECT 1"))
    except SQLAlchemyError:
        raise ApiError(503, "SERVICE_UNAVAILABLE", "La base de datos no esta disponible.") from None
    return {"status": "ready"}

import uuid
import logging
from datetime import datetime, timezone
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Header, Query, Request, Response, status
from sqlalchemy import select, text, update
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.database import get_db
from app.errors import ApiError
from app.models import Assignment, Parking, Spot
from app.logging_config import log_event
from app.outbox import add_spot_event, availability, spot_snapshot
from app.schemas import AssignmentCreate, AssignmentRead, ParkingRead, SpotRead
from app.security import authenticated_claims, require_reservations_service


public_router = APIRouter(
    prefix="/api/v1/parkings",
    tags=["parkings"],
    dependencies=[Depends(authenticated_claims)],
)
internal_router = APIRouter(
    prefix="/internal/v1/asignaciones",
    tags=["internal-assignments"],
    dependencies=[Depends(require_reservations_service)],
)
health_router = APIRouter(tags=["health"])
logger = logging.getLogger("parkings.domain")


def parking_read(parking: Parking) -> ParkingRead:
    return ParkingRead(id=parking.id, name=parking.name, address=parking.address, created_at=parking.created_at)


def spot_read(spot: Spot) -> SpotRead:
    return SpotRead(**spot_snapshot(spot))


def assignment_read(value: Assignment) -> AssignmentRead:
    return AssignmentRead(
        reservation_id=value.reservation_id,
        parking_id=value.parking_id,
        spot_id=value.spot_id,
        operation_id=value.operation_id,
        status=value.status,
        reason=value.reason,
        version=value.version,
        updated_at=value.updated_at,
    )


def lock_assignment(session: Session, reservation_id: str) -> None:
    if session.bind is not None and session.bind.dialect.name == "postgresql":
        session.execute(text("SELECT pg_advisory_xact_lock(hashtext(:reservation_id))"), {"reservation_id": reservation_id})


def unavailable_error(assignment: Assignment) -> ApiError:
    details = {"reason": assignment.reason, "reservation_id": assignment.reservation_id}
    if assignment.reason in {"parking_not_found", "spot_not_found"}:
        return ApiError(404, "RESOURCE_NOT_FOUND", "El estacionamiento o la plaza no existe.", details)
    return ApiError(409, "SPOT_UNAVAILABLE", "La plaza no esta disponible.", details)


@public_router.get("", response_model=list[ParkingRead])
def list_parkings(db: Annotated[Session, Depends(get_db)]) -> list[ParkingRead]:
    values = db.scalars(select(Parking).order_by(Parking.created_at, Parking.id)).all()
    return [parking_read(value) for value in values]


@public_router.get("/{parking_id}", response_model=ParkingRead)
def get_parking(parking_id: uuid.UUID, db: Annotated[Session, Depends(get_db)]) -> ParkingRead:
    parking = db.get(Parking, str(parking_id))
    if parking is None:
        raise ApiError(404, "RESOURCE_NOT_FOUND", "El estacionamiento no existe.")
    return parking_read(parking)


@public_router.get("/{parking_id}/plazas", response_model=list[SpotRead])
def list_spots(
    parking_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
    requested_availability: Annotated[
        Literal["available", "reserved", "occupied", "unknown"] | None,
        Query(alias="availability"),
    ] = None,
) -> list[SpotRead]:
    parking = db.get(Parking, str(parking_id))
    if parking is None:
        raise ApiError(404, "RESOURCE_NOT_FOUND", "El estacionamiento no existe.")
    spots = db.scalars(select(Spot).where(Spot.parking_id == str(parking_id)).order_by(Spot.label, Spot.id)).all()
    if requested_availability is not None:
        spots = [spot for spot in spots if availability(spot) == requested_availability]
    return [spot_read(spot) for spot in spots]


@public_router.get("/{parking_id}/plazas/{spot_id}", response_model=SpotRead)
def get_spot(parking_id: uuid.UUID, spot_id: uuid.UUID, db: Annotated[Session, Depends(get_db)]) -> SpotRead:
    spot = db.scalar(select(Spot).where(Spot.id == str(spot_id), Spot.parking_id == str(parking_id)))
    if spot is None:
        raise ApiError(404, "RESOURCE_NOT_FOUND", "La plaza no existe en ese estacionamiento.")
    return spot_read(spot)


@internal_router.put("/{reservation_id}", response_model=AssignmentRead)
def assign_spot(
    reservation_id: uuid.UUID,
    payload: AssignmentCreate,
    request: Request,
    response: Response,
    db: Annotated[Session, Depends(get_db)],
) -> AssignmentRead:
    reservation_value = str(reservation_id)
    parking_value = str(payload.parking_id)
    spot_value = str(payload.spot_id)
    operation_value = str(payload.operation_id)
    now = datetime.now(timezone.utc)
    lock_assignment(db, reservation_value)
    existing = db.get(Assignment, reservation_value)
    if existing is not None:
        if existing.status == "released":
            log_event(
                logger,
                "assignment_rejected",
                "conflict",
                level=logging.WARNING,
                correlation_id=request.state.correlation_id,
                reservation_id=reservation_value,
                operation_id=operation_value,
                error_code="ASSIGNMENT_CLOSED",
            )
            raise ApiError(409, "ASSIGNMENT_CLOSED", "La asignacion ya fue cerrada.")
        if (existing.parking_id, existing.spot_id, existing.operation_id) != (parking_value, spot_value, operation_value):
            log_event(
                logger,
                "assignment_rejected",
                "conflict",
                level=logging.WARNING,
                correlation_id=request.state.correlation_id,
                reservation_id=reservation_value,
                operation_id=operation_value,
                error_code="IDEMPOTENCY_KEY_REUSED",
            )
            raise ApiError(409, "IDEMPOTENCY_KEY_REUSED", "La asignacion ya fue solicitada con otros datos.")
        if existing.status == "assigned":
            response.status_code = status.HTTP_200_OK
            log_event(
                logger,
                "assignment_created",
                "duplicate",
                correlation_id=request.state.correlation_id,
                reservation_id=reservation_value,
                spot_id=spot_value,
                operation_id=operation_value,
                entity_version=existing.version,
            )
            return assignment_read(existing)
        log_event(
            logger,
            "assignment_rejected",
            "duplicate_rejection",
            level=logging.WARNING,
            correlation_id=request.state.correlation_id,
            reservation_id=reservation_value,
            spot_id=spot_value,
            operation_id=operation_value,
            error_code="SPOT_UNAVAILABLE",
            reason=existing.reason,
        )
        raise unavailable_error(existing)

    if db.get(Parking, parking_value) is None:
        rejected = Assignment(
            reservation_id=reservation_value,
            parking_id=parking_value,
            spot_id=spot_value,
            operation_id=operation_value,
            status="rejected",
            reason="parking_not_found",
            updated_at=now,
        )
        db.add(rejected)
        db.commit()
        log_event(
            logger,
            "assignment_rejected",
            "not_found",
            level=logging.WARNING,
            correlation_id=request.state.correlation_id,
            reservation_id=reservation_value,
            spot_id=spot_value,
            operation_id=operation_value,
            error_code="RESOURCE_NOT_FOUND",
        )
        raise unavailable_error(rejected)

    spot = db.scalar(select(Spot).where(Spot.id == spot_value, Spot.parking_id == parking_value))
    if spot is None:
        rejected = Assignment(
            reservation_id=reservation_value,
            parking_id=parking_value,
            spot_id=spot_value,
            operation_id=operation_value,
            status="rejected",
            reason="spot_not_found",
            updated_at=now,
        )
        db.add(rejected)
        db.commit()
        log_event(
            logger,
            "assignment_rejected",
            "not_found",
            level=logging.WARNING,
            correlation_id=request.state.correlation_id,
            reservation_id=reservation_value,
            spot_id=spot_value,
            operation_id=operation_value,
            error_code="RESOURCE_NOT_FOUND",
        )
        raise unavailable_error(rejected)

    result = db.execute(
        update(Spot)
        .where(
            Spot.id == spot_value,
            Spot.parking_id == parking_value,
            Spot.physical_occupied.is_(False),
            Spot.assigned_reservation_id.is_(None),
            Spot.sensor_status == "fresh",
            Spot.sensor_expires_at.is_not(None),
            Spot.sensor_expires_at > now,
        )
        .values(
            assigned_reservation_id=reservation_value,
            version=Spot.version + 1,
            updated_at=now,
        )
        .execution_options(synchronize_session=False)
    )
    if result.rowcount != 1:
        db.refresh(spot)
        if availability(spot, now) == "unknown":
            reason = "sensor_stale"
        elif spot.physical_occupied:
            reason = "occupied"
        else:
            reason = "assigned"
        rejected = Assignment(
            reservation_id=reservation_value,
            parking_id=parking_value,
            spot_id=spot_value,
            operation_id=operation_value,
            status="rejected",
            reason=reason,
            updated_at=now,
        )
        db.add(rejected)
        db.commit()
        log_event(
            logger,
            "assignment_rejected",
            "conflict",
            level=logging.WARNING,
            correlation_id=request.state.correlation_id,
            reservation_id=reservation_value,
            spot_id=spot_value,
            operation_id=operation_value,
            error_code="SPOT_UNAVAILABLE",
            reason=reason,
        )
        raise unavailable_error(rejected)

    assigned = Assignment(
        reservation_id=reservation_value,
        parking_id=parking_value,
        spot_id=spot_value,
        operation_id=operation_value,
        status="assigned",
        updated_at=now,
    )
    db.add(assigned)
    db.flush()
    db.refresh(spot)
    add_spot_event(db, spot, "parking.availability_changed.v1", "assignment_created", request.state.correlation_id)
    db.commit()
    response.status_code = status.HTTP_201_CREATED
    log_event(
        logger,
        "assignment_created",
        "success",
        correlation_id=request.state.correlation_id,
        reservation_id=reservation_value,
        spot_id=spot_value,
        operation_id=operation_value,
        entity_version=assigned.version,
    )
    return assignment_read(assigned)


@internal_router.get("/{reservation_id}", response_model=AssignmentRead)
def get_assignment(reservation_id: uuid.UUID, db: Annotated[Session, Depends(get_db)]) -> AssignmentRead:
    value = db.get(Assignment, str(reservation_id))
    if value is None:
        raise ApiError(404, "RESOURCE_NOT_FOUND", "La asignacion no existe.")
    return assignment_read(value)


@internal_router.delete("/{reservation_id}", response_model=AssignmentRead)
def release_assignment(
    reservation_id: uuid.UUID,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> AssignmentRead:
    try:
        release_operation_id = str(uuid.UUID(idempotency_key)) if idempotency_key else None
    except ValueError:
        release_operation_id = None
    if release_operation_id is None:
        raise ApiError(400, "INVALID_IDEMPOTENCY_KEY", "Idempotency-Key debe ser un UUID.")

    reservation_value = str(reservation_id)
    now = datetime.now(timezone.utc)
    lock_assignment(db, reservation_value)
    assignment = db.get(Assignment, reservation_value)
    if assignment is not None and assignment.status == "released":
        if assignment.release_operation_id != release_operation_id:
            log_event(
                logger,
                "assignment_rejected",
                "conflict",
                level=logging.WARNING,
                correlation_id=request.state.correlation_id,
                reservation_id=reservation_value,
                operation_id=release_operation_id,
                error_code="IDEMPOTENCY_KEY_REUSED",
            )
            raise ApiError(409, "IDEMPOTENCY_KEY_REUSED", "La liberacion ya uso otra clave.")
        log_event(
            logger,
            "assignment_released",
            "duplicate",
            correlation_id=request.state.correlation_id,
            reservation_id=reservation_value,
            operation_id=release_operation_id,
            entity_version=assignment.version,
        )
        return assignment_read(assignment)

    if assignment is None:
        assignment = Assignment(
            reservation_id=reservation_value,
            status="released",
            release_operation_id=release_operation_id,
            updated_at=now,
        )
        db.add(assignment)
        db.commit()
        log_event(
            logger,
            "assignment_released",
            "closed_before_assignment",
            correlation_id=request.state.correlation_id,
            reservation_id=reservation_value,
            operation_id=release_operation_id,
            entity_version=assignment.version,
        )
        return assignment_read(assignment)

    changed_spot = None
    if assignment.status == "assigned" and assignment.spot_id is not None:
        assigned_spot = db.scalar(select(Spot).where(Spot.id == assignment.spot_id).with_for_update())
        if assigned_spot is not None and assigned_spot.physical_occupied is True:
            raise ApiError(
                409,
                "RESERVATION_IN_USE",
                "La reserva no se puede cancelar mientras la plaza esta ocupada.",
                {"reason": "occupied", "reservation_id": reservation_value},
            )
        result = db.execute(
            update(Spot)
            .where(Spot.id == assignment.spot_id, Spot.assigned_reservation_id == reservation_value)
            .values(assigned_reservation_id=None, version=Spot.version + 1, updated_at=now)
            .execution_options(synchronize_session=False)
        )
        if result.rowcount == 1:
            changed_spot = db.get(Spot, assignment.spot_id)
            db.refresh(changed_spot)

    assignment.status = "released"
    assignment.reason = None
    assignment.release_operation_id = release_operation_id
    assignment.version += 1
    assignment.updated_at = now
    if changed_spot is not None:
        add_spot_event(db, changed_spot, "parking.availability_changed.v1", "assignment_released", request.state.correlation_id)
    db.commit()
    log_event(
        logger,
        "assignment_released",
        "success",
        correlation_id=request.state.correlation_id,
        reservation_id=reservation_value,
        spot_id=assignment.spot_id,
        operation_id=release_operation_id,
        entity_version=assignment.version,
    )
    return assignment_read(assignment)


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

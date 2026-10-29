import base64
import binascii
from datetime import datetime, timezone
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.database import get_db
from app.errors import ApiError
from app.models import ReservationProjection, SpotProjection
from app.schemas import AlertsCollection, MetricsSummary, Occupancy, ReservationCounts, SensorAlert, SpotCounts
from app.security import require_admin


public_router = APIRouter(prefix="/api/v1/metricas", tags=["metricas"], dependencies=[Depends(require_admin)])
health_router = APIRouter(tags=["health"])


def aware(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def is_fresh(value: SpotProjection, now: datetime) -> bool:
    expires_at = aware(value.sensor_expires_at)
    return value.sensor_status == "fresh" and expires_at is not None and now < expires_at \
        and value.physical_occupied is not None


def effective_availability(value: SpotProjection, now: datetime) -> str:
    if not is_fresh(value, now):
        return "unknown"
    if value.physical_occupied:
        return "occupied"
    if value.assigned_reservation_id is not None:
        return "reserved"
    return "available"


def projections(db: Session, parking_id: UUID | None) -> tuple[list[SpotProjection], list[ReservationProjection]]:
    spot_query = select(SpotProjection)
    reservation_query = select(ReservationProjection)
    if parking_id is not None:
        spot_query = spot_query.where(SpotProjection.parking_id == str(parking_id))
        reservation_query = reservation_query.where(ReservationProjection.parking_id == str(parking_id))
    spots = list(db.scalars(spot_query).all())
    if parking_id is not None and not spots:
        raise ApiError(404, "RESOURCE_NOT_FOUND", "No existe proyeccion para ese estacionamiento.")
    return spots, list(db.scalars(reservation_query).all())


@public_router.get("/resumen", response_model=MetricsSummary)
def summary(
    db: Annotated[Session, Depends(get_db)],
    parking_id: UUID | None = None,
) -> MetricsSummary:
    now = datetime.now(timezone.utc)
    spots, reservations = projections(db, parking_id)
    categories = [effective_availability(value, now) for value in spots]
    fresh = [value for value in spots if is_fresh(value, now)]
    occupied_fresh = sum(value.physical_occupied is True for value in fresh)
    fresh_total = len(fresh)
    projected = [aware(value.projected_at) for value in [*spots, *reservations] if value.projected_at]
    return MetricsSummary(
        parking_id=parking_id,
        spots=SpotCounts(
            total=len(spots),
            available=categories.count("available"), reserved=categories.count("reserved"),
            occupied=categories.count("occupied"), unknown=categories.count("unknown"),
            assigned_total=sum(value.assigned_reservation_id is not None for value in spots),
            physically_occupied_fresh=occupied_fresh,
        ),
        reservations=ReservationCounts(
            confirmed_current=sum(value.status in {"confirmed", "occupied"} for value in reservations),
            created_total=sum(value.ever_confirmed for value in reservations),
            cancelled_total=sum(value.status == "cancelled" and value.ever_confirmed for value in reservations),
        ),
        occupancy=Occupancy(
            occupied_fresh=occupied_fresh, fresh_total=fresh_total,
            percentage=round(100 * occupied_fresh / fresh_total, 2) if fresh_total else None,
        ),
        last_projected_at=max(projected) if projected else None,
        computed_at=now,
    )


def encode_cursor(value: SpotProjection) -> str:
    return base64.urlsafe_b64encode(f"{value.parking_id}|{value.id}".encode()).decode()


def decode_cursor(cursor: str) -> tuple[str, str]:
    try:
        parking_id, spot_id = base64.urlsafe_b64decode(cursor.encode()).decode().split("|", 1)
        return str(UUID(parking_id)), str(UUID(spot_id))
    except (binascii.Error, UnicodeError, ValueError):
        raise ApiError(400, "INVALID_CURSOR", "El cursor no es valido.") from None


@public_router.get("/alertas", response_model=AlertsCollection)
def alerts(
    db: Annotated[Session, Depends(get_db)],
    parking_id: UUID | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    cursor: str | None = None,
) -> AlertsCollection:
    now = datetime.now(timezone.utc)
    spots, _ = projections(db, parking_id)
    spots.sort(key=lambda value: (value.parking_id, value.id))
    if cursor:
        after = decode_cursor(cursor)
        spots = [value for value in spots if (value.parking_id, value.id) > after]
    stale = [value for value in spots if not is_fresh(value, now)]
    page = stale[:limit]
    return AlertsCollection(
        items=[SensorAlert(
            spot_id=value.id, parking_id=value.parking_id, sensor_id=value.sensor_id,
            label=value.label,
            since=aware(value.sensor_expires_at) or aware(value.initialized_at),
            last_report_at=aware(value.last_report_at),
        ) for value in page],
        next_cursor=encode_cursor(page[-1]) if len(stale) > limit else None,
        computed_at=now,
    )


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

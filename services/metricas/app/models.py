from datetime import datetime, timezone

from sqlalchemy import Boolean, CheckConstraint, DateTime, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class SpotProjection(Base):
    __tablename__ = "spot_projections"
    __table_args__ = (
        CheckConstraint("sensor_status IN ('fresh', 'stale')", name="ck_metric_spot_sensor_status"),
        CheckConstraint(
            "availability IN ('available', 'reserved', 'occupied', 'unknown')",
            name="ck_metric_spot_availability",
        ),
        Index("ix_metric_spots_parking_id", "parking_id", "id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    parking_id: Mapped[str] = mapped_column(String(36), nullable=False)
    sensor_id: Mapped[str] = mapped_column(String(36), nullable=False)
    label: Mapped[str] = mapped_column(String(100), nullable=False)
    physical_occupied: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    assigned_reservation_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    sensor_status: Mapped[str] = mapped_column(String(16), nullable=False)
    last_report_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    sensor_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    availability: Mapped[str] = mapped_column(String(16), nullable=False)
    version: Mapped[int] = mapped_column(nullable=False)
    initialized_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    source_updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    projected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)


class ReservationProjection(Base):
    __tablename__ = "reservation_projections"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'confirmed', 'occupied', 'used', 'cancel_pending', 'cancelled', 'rejected')",
            name="ck_metric_reservation_status",
        ),
        Index("ix_metric_reservations_parking_id", "parking_id", "id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(36), nullable=False)
    parking_id: Mapped[str] = mapped_column(String(36), nullable=False)
    spot_id: Mapped[str] = mapped_column(String(36), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False)
    ever_confirmed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    source_updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    failure_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    version: Mapped[int] = mapped_column(nullable=False)
    projected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)


class SpotUsageRecord(Base):
    __tablename__ = "spot_usage_records"
    __table_args__ = (
        Index("ix_spot_usage_parking_used", "parking_id", "used_at"),
        Index("ix_spot_usage_spot_used", "spot_id", "used_at"),
    )

    reservation_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    event_id: Mapped[str] = mapped_column(String(36), nullable=False, unique=True)
    parking_id: Mapped[str] = mapped_column(String(36), nullable=False)
    spot_id: Mapped[str] = mapped_column(String(36), nullable=False)
    used_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    projected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)


class ProcessedEvent(Base):
    __tablename__ = "processed_events"

    consumer_name: Mapped[str] = mapped_column(String(100), primary_key=True)
    event_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    processed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)

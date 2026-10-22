import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Parking(Base):
    __tablename__ = "parkings"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String(100))
    address: Mapped[str] = mapped_column(String(250))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    spots: Mapped[list["Spot"]] = relationship(back_populates="parking")


class Spot(Base):
    __tablename__ = "spots"
    __table_args__ = (
        UniqueConstraint("parking_id", "label", name="uq_spots_parking_label"),
        UniqueConstraint("sensor_id", name="uq_spots_sensor_id"),
        CheckConstraint("sensor_status IN ('fresh', 'stale')", name="ck_spots_sensor_status"),
        Index("ix_spots_parking_id_id", "parking_id", "id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    parking_id: Mapped[str] = mapped_column(ForeignKey("parkings.id", ondelete="CASCADE"))
    sensor_id: Mapped[str] = mapped_column(String(36))
    label: Mapped[str] = mapped_column(String(100))
    physical_occupied: Mapped[bool] = mapped_column(Boolean, nullable=True)
    assigned_reservation_id: Mapped[str] = mapped_column(String(36), nullable=True, index=True)
    sensor_status: Mapped[str] = mapped_column(String(16), default="stale", server_default="stale")
    last_sequence: Mapped[int] = mapped_column(Integer, nullable=True)
    last_report_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    sensor_expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    version: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    parking: Mapped[Parking] = relationship(back_populates="spots")


class Assignment(Base):
    __tablename__ = "assignments"
    __table_args__ = (CheckConstraint("status IN ('assigned', 'rejected', 'released')", name="ck_assignments_status"),)

    reservation_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    parking_id: Mapped[str] = mapped_column(String(36), nullable=True)
    spot_id: Mapped[str] = mapped_column(String(36), nullable=True)
    operation_id: Mapped[str] = mapped_column(String(36), nullable=True)
    release_operation_id: Mapped[str] = mapped_column(String(36), nullable=True)
    status: Mapped[str] = mapped_column(String(16))
    reason: Mapped[str] = mapped_column(String(32), nullable=True)
    version: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class OutboxEvent(Base):
    __tablename__ = "outbox_events"
    __table_args__ = (Index("ix_outbox_unpublished", "published_at", "created_at"),)

    event_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    event_type: Mapped[str] = mapped_column(String(100))
    correlation_id: Mapped[str] = mapped_column(String(36))
    payload: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    last_error: Mapped[str] = mapped_column(Text, nullable=True)


class ProcessedEvent(Base):
    __tablename__ = "processed_events"

    consumer_name: Mapped[str] = mapped_column(String(100), primary_key=True)
    event_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    processed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

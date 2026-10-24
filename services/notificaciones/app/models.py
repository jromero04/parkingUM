import uuid
from datetime import datetime, timezone

from sqlalchemy import CheckConstraint, DateTime, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Delivery(Base):
    __tablename__ = "deliveries"
    __table_args__ = (
        UniqueConstraint("event_id", "channel", name="uq_deliveries_event_channel"),
        CheckConstraint("status IN ('delivered', 'suppressed')", name="ck_deliveries_status"),
        CheckConstraint(
            "template IN ('reservation_confirmed', 'reservation_cancelled', 'request_cancelled')",
            name="ck_deliveries_template",
        ),
        Index("ix_deliveries_reservation_version", "reservation_id", "reservation_version"),
    )
    delivery_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    event_id: Mapped[str] = mapped_column(String(36), nullable=False)
    reservation_id: Mapped[str] = mapped_column(String(36), nullable=False)
    reservation_version: Mapped[int] = mapped_column(Integer, nullable=False)
    user_id: Mapped[str] = mapped_column(String(36), nullable=False)
    template: Mapped[str] = mapped_column(String(32), nullable=False)
    channel: Mapped[str] = mapped_column(String(32), nullable=False, default="simulated_email")
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ReservationState(Base):
    __tablename__ = "reservation_states"
    reservation_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    highest_version: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False)
    ever_confirmed: Mapped[bool] = mapped_column(nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)


class ProcessedEvent(Base):
    __tablename__ = "processed_events"
    consumer_name: Mapped[str] = mapped_column(String(100), primary_key=True)
    event_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    processed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)

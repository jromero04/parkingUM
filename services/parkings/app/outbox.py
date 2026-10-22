import json
import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models import OutboxEvent, Spot


def availability(spot: Spot, now: datetime | None = None) -> str:
    now = now or datetime.now(timezone.utc)
    expires_at = spot.sensor_expires_at
    if expires_at is not None and expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    fresh = spot.sensor_status == "fresh" and expires_at is not None and now < expires_at
    if not fresh or spot.physical_occupied is None:
        return "unknown"
    if spot.physical_occupied:
        return "occupied"
    if spot.assigned_reservation_id is not None:
        return "reserved"
    return "available"


def spot_snapshot(spot: Spot, now: datetime | None = None) -> dict:
    effective_status = "fresh" if availability(spot, now) != "unknown" else "stale"
    return {
        "id": spot.id,
        "parking_id": spot.parking_id,
        "sensor_id": spot.sensor_id,
        "label": spot.label,
        "physical_occupied": spot.physical_occupied,
        "assigned_reservation_id": spot.assigned_reservation_id,
        "sensor_status": effective_status,
        "last_report_at": spot.last_report_at.isoformat() if spot.last_report_at else None,
        "sensor_expires_at": spot.sensor_expires_at.isoformat() if spot.sensor_expires_at else None,
        "availability": availability(spot, now),
        "version": spot.version,
        "updated_at": spot.updated_at.isoformat(),
    }


def add_spot_event(session: Session, spot: Spot, event_type: str, reason: str, correlation_id: str) -> None:
    occurred_at = datetime.now(timezone.utc)
    event_id = str(uuid.uuid4())
    envelope = {
        "event_id": event_id,
        "event_type": event_type,
        "schema_version": 1,
        "occurred_at": occurred_at.isoformat(),
        "producer": "parkings",
        "correlation_id": correlation_id,
        "data": {"spot": spot_snapshot(spot, occurred_at), "reason": reason},
    }
    session.add(
        OutboxEvent(
            event_id=event_id,
            event_type=event_type,
            correlation_id=correlation_id,
            payload=json.dumps(envelope),
            created_at=occurred_at,
        )
    )

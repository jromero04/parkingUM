import logging
import os
import socket
import time
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import or_, select

from app.config import get_settings
from app.database import SessionLocal
from app.domain import attempt_pending
from app.logging_config import configure_logging, log_event
from app.models import Reservation
from app.parking_client import ParkingClient


configure_logging("reservas-recovery")
logger = logging.getLogger("reservas.recovery")
worker_id = f"{socket.gethostname()}:{os.getpid()}:{uuid.uuid4()}"


def claim_one() -> str | None:
    settings = get_settings()
    now = datetime.now(timezone.utc)
    with SessionLocal() as db:
        value = db.scalar(
            select(Reservation).where(
                Reservation.status.in_(("pending", "cancel_pending")),
                Reservation.next_attempt_at <= now,
                or_(Reservation.lease_until.is_(None), Reservation.lease_until <= now),
            ).order_by(Reservation.next_attempt_at, Reservation.created_at)
            .limit(1).with_for_update(skip_locked=True)
        )
        if value is None:
            return None
        value.lease_owner = worker_id
        value.lease_until = now + timedelta(seconds=settings.recovery_lease_seconds)
        reservation_id = value.id
        db.commit()
        return reservation_id


def run() -> None:
    settings = get_settings()
    client = ParkingClient()
    while True:
        try:
            reservation_id = claim_one()
            if reservation_id is None:
                time.sleep(settings.recovery_poll_seconds)
                continue
            with SessionLocal() as db:
                value = attempt_pending(db, reservation_id, client)
                if value.attempt_count and value.last_attempt_at and value.created_at:
                    age = datetime.now(timezone.utc) - value.created_at.replace(tzinfo=value.created_at.tzinfo or timezone.utc)
                    if age.total_seconds() >= 60 and value.status in {"pending", "cancel_pending"}:
                        log_event(logger, "recovery_attempted", "pending_alert", level=logging.WARNING,
                                  correlation_id=value.correlation_id, reservation_id=value.id,
                                  attempt=value.attempt_count)
        except Exception:
            logger.exception("Fallo el recuperador de reservas",
                             extra={"action": "event_failed", "result": "retry", "correlation_id": None})
            time.sleep(settings.recovery_poll_seconds)


if __name__ == "__main__":
    run()

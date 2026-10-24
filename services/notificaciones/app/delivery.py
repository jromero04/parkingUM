from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.models import Delivery, ProcessedEvent, ReservationState
from app.recipient_client import RecipientClient
from app.schemas import EventEnvelope


CONSUMER_NAME = "notificaciones"


@dataclass(frozen=True)
class DeliveryResult:
    status: str
    delivery_id: str | None = None
    template: str | None = None


def process_event(session: Session, envelope: EventEnvelope, recipients: RecipientClient) -> DeliveryResult:
    event_id = str(envelope.event_id)
    existing = session.scalar(select(Delivery).where(
        Delivery.event_id == event_id, Delivery.channel == "simulated_email"
    ))
    if existing is not None or session.get(ProcessedEvent, (CONSUMER_NAME, event_id)) is not None:
        return DeliveryResult("duplicate", existing.delivery_id if existing else None,
                              existing.template if existing else None)
    snapshot = envelope.data.reservation
    if envelope.event_type == "reservation.created.v1" and snapshot.status != "confirmed":
        raise ValueError("created requiere confirmed")
    if envelope.event_type == "reservation.cancelled.v1" and snapshot.status != "cancelled":
        raise ValueError("cancelled requiere cancelled")
    reservation_id = str(snapshot.id)
    if session.bind is not None and session.bind.dialect.name == "postgresql":
        session.execute(text("SELECT pg_advisory_xact_lock(hashtext(:value))"), {"value": reservation_id})
    state = session.scalar(select(ReservationState).where(
        ReservationState.reservation_id == reservation_id
    ).with_for_update())
    template = "reservation_confirmed" if envelope.event_type == "reservation.created.v1" else (
        "reservation_cancelled" if snapshot.ever_confirmed else "request_cancelled"
    )
    outdated = state is not None and state.highest_version >= snapshot.version
    now = datetime.now(timezone.utc)
    if not outdated:
        recipient = recipients.get(str(snapshot.user_id), str(envelope.correlation_id))
        if str(recipient.user_id) != str(snapshot.user_id):
            raise ValueError("destinatario no coincide")
    delivery = Delivery(
        event_id=event_id, reservation_id=reservation_id, reservation_version=snapshot.version,
        user_id=str(snapshot.user_id), template=template, channel="simulated_email",
        status="suppressed" if outdated else "delivered", created_at=now,
        delivered_at=None if outdated else now,
    )
    session.add(delivery)
    session.add(ProcessedEvent(consumer_name=CONSUMER_NAME, event_id=event_id, processed_at=now))
    if not outdated:
        if state is None:
            state = ReservationState(reservation_id=reservation_id, highest_version=snapshot.version,
                                     status=snapshot.status, ever_confirmed=snapshot.ever_confirmed,
                                     updated_at=now)
            session.add(state)
        else:
            state.highest_version = snapshot.version
            state.status = snapshot.status
            state.ever_confirmed = snapshot.ever_confirmed
            state.updated_at = now
    session.flush()
    return DeliveryResult(delivery.status, delivery.delivery_id, template)

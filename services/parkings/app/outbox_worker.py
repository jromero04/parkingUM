import logging
import time
from datetime import datetime, timezone

import pika
from sqlalchemy import select

from app.broker import PARKING_EXCHANGE, connection, declare_topology
from app.database import SessionLocal
from app.logging_config import configure_logging, log_event
from app.models import OutboxEvent


configure_logging("parkings-outbox")
logger = logging.getLogger("parkings.outbox")


def run() -> None:
    while True:
        broker = None
        try:
            broker = connection()
            channel = broker.channel()
            declare_topology(channel)
            channel.confirm_delivery()
            while True:
                with SessionLocal() as db:
                    event = db.scalar(
                        select(OutboxEvent)
                        .where(OutboxEvent.published_at.is_(None))
                        .order_by(OutboxEvent.created_at)
                        .limit(1)
                    )
                    if event is None:
                        time.sleep(0.5)
                        continue
                    try:
                        channel.basic_publish(
                            exchange=PARKING_EXCHANGE,
                            routing_key=event.event_type,
                            body=event.payload.encode("utf-8"),
                            mandatory=True,
                            properties=pika.BasicProperties(
                                content_type="application/json",
                                delivery_mode=2,
                                message_id=event.event_id,
                                correlation_id=event.correlation_id,
                                type=event.event_type,
                            ),
                        )
                        event.published_at = datetime.now(timezone.utc)
                        event.attempts += 1
                        event.last_error = None
                        db.commit()
                        log_event(
                            logger,
                            "event_published",
                            "success",
                            correlation_id=event.correlation_id,
                            event_id=event.event_id,
                            event_type=event.event_type,
                            attempt=event.attempts,
                        )
                    except Exception as exc:
                        event.attempts += 1
                        event.last_error = str(exc)[:1000]
                        db.commit()
                        raise
        except Exception:
            logger.exception(
                "El relay de outbox se reconectara",
                extra={"action": "recovery_attempted", "result": "retry", "correlation_id": None},
            )
            if broker is not None and broker.is_open:
                broker.close()
            time.sleep(5)


if __name__ == "__main__":
    run()

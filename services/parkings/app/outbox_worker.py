import logging
import time
from datetime import datetime, timezone

import pika
from sqlalchemy import select

from app.broker import PARKING_EXCHANGE, connection, declare_topology
from app.database import SessionLocal
from app.models import OutboxEvent


logging.basicConfig(level=logging.INFO, format="%(message)s")
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
                    except Exception as exc:
                        event.attempts += 1
                        event.last_error = str(exc)[:1000]
                        db.commit()
                        raise
        except Exception:
            logger.exception("El relay de outbox se reconectara")
            if broker is not None and broker.is_open:
                broker.close()
            time.sleep(5)


if __name__ == "__main__":
    run()

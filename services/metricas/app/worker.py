import json
import logging
import time

from pydantic import ValidationError

from app.broker import (
    PARKING_QUEUE, RESERVATIONS_QUEUE, RETRY_DELAYS, connection, declare_topology, publish_retry,
)
from app.database import SessionLocal
from app.logging_config import configure_logging, log_event
from app.projection import UnsupportedEventError, process_event
from app.schemas import EventEnvelope


configure_logging("metricas-worker")
logger = logging.getLogger("metricas.worker")


def run() -> None:
    while True:
        broker = None
        try:
            broker = connection()
            channel = broker.channel()
            declare_topology(channel)
            channel.confirm_delivery()
            channel.basic_qos(prefetch_count=1)

            def callback(queue, ch, method, properties, body):
                try:
                    envelope = EventEnvelope.model_validate(json.loads(body.decode("utf-8")))
                    with SessionLocal() as db:
                        result = process_event(db, envelope)
                        db.commit()
                    action = {"duplicate": "event_duplicate", "discarded": "event_discarded"}.get(
                        result.status, "event_processed"
                    )
                    level = logging.WARNING if result.status == "discarded" else logging.INFO
                    log_event(logger, action, result.status, level=level,
                              correlation_id=str(envelope.correlation_id), event_id=str(envelope.event_id),
                              event_type=envelope.event_type, entity_id=result.entity_id,
                              entity_version=result.version)
                    ch.basic_ack(method.delivery_tag)
                except (json.JSONDecodeError, UnicodeDecodeError, ValidationError, UnsupportedEventError, ValueError):
                    logger.exception("Evento invalido enviado a DLQ",
                                     extra={"action": "event_failed", "result": "dlq",
                                            "correlation_id": properties.correlation_id})
                    ch.basic_reject(method.delivery_tag, requeue=False)
                except Exception:
                    attempt = int((properties.headers or {}).get("x-retry-count", 0))
                    if attempt >= len(RETRY_DELAYS):
                        logger.exception("Evento agotó reintentos",
                                         extra={"action": "event_failed", "result": "dlq",
                                                "correlation_id": properties.correlation_id,
                                                "attempt": attempt + 1})
                        ch.basic_reject(method.delivery_tag, requeue=False)
                    else:
                        logger.exception("Fallo transitorio proyectando evento",
                                         extra={"action": "event_failed", "result": "retry",
                                                "correlation_id": properties.correlation_id,
                                                "attempt": attempt + 1})
                        publish_retry(ch, queue, body, properties, attempt)
                        ch.basic_ack(method.delivery_tag)

            channel.basic_consume(
                queue=PARKING_QUEUE,
                on_message_callback=lambda ch, method, properties, body: callback(
                    PARKING_QUEUE, ch, method, properties, body
                ),
                auto_ack=False,
            )
            channel.basic_consume(
                queue=RESERVATIONS_QUEUE,
                on_message_callback=lambda ch, method, properties, body: callback(
                    RESERVATIONS_QUEUE, ch, method, properties, body
                ),
                auto_ack=False,
            )
            channel.start_consuming()
        except Exception:
            logger.exception("El consumidor de metricas se reconectara",
                             extra={"action": "recovery_attempted", "result": "retry", "correlation_id": None})
            if broker is not None and broker.is_open:
                broker.close()
            time.sleep(5)


if __name__ == "__main__":
    run()

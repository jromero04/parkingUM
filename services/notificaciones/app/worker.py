import json
import logging
import time

from pydantic import ValidationError

from app.broker import QUEUE, RETRY_DELAYS, connection, declare_topology, retry
from app.database import SessionLocal
from app.delivery import process_event
from app.logging_config import configure_logging, log_event
from app.recipient_client import PermanentRecipientError, RecipientClient, TransientRecipientError
from app.schemas import EventEnvelope


configure_logging("notificaciones-worker")
logger = logging.getLogger("notificaciones.worker")


def run() -> None:
    recipients = RecipientClient()
    while True:
        broker = None
        try:
            broker = connection(); channel = broker.channel(); declare_topology(channel)
            channel.confirm_delivery(); channel.basic_qos(prefetch_count=1)
            def callback(ch, method, properties, body):
                try:
                    envelope = EventEnvelope.model_validate(json.loads(body.decode()))
                    with SessionLocal() as db:
                        result = process_event(db, envelope, recipients); db.commit()
                    action = "event_duplicate" if result.status == "duplicate" else (
                        "event_discarded" if result.status == "suppressed" else "notification_delivered")
                    log_event(logger, action, result.status,
                              level=logging.WARNING if result.status == "suppressed" else logging.INFO,
                              correlation_id=str(envelope.correlation_id), event_id=str(envelope.event_id),
                              reservation_id=str(envelope.data.reservation.id),
                              entity_version=envelope.data.reservation.version,
                              delivery_id=result.delivery_id, template=result.template)
                    ch.basic_ack(method.delivery_tag)
                except (json.JSONDecodeError, UnicodeDecodeError, ValidationError, PermanentRecipientError, ValueError):
                    logger.exception("Notificacion invalida enviada a DLQ",
                                     extra={"action": "event_failed", "result": "dlq",
                                            "correlation_id": properties.correlation_id})
                    ch.basic_reject(method.delivery_tag, requeue=False)
                except Exception:
                    attempt = int((properties.headers or {}).get("x-retry-count", 0))
                    if attempt >= len(RETRY_DELAYS):
                        logger.exception("Notificacion agoto reintentos",
                                         extra={"action": "event_failed", "result": "dlq",
                                                "correlation_id": properties.correlation_id})
                        ch.basic_reject(method.delivery_tag, requeue=False)
                    else:
                        retry(ch, body, properties, attempt); ch.basic_ack(method.delivery_tag)
            channel.basic_consume(queue=QUEUE, on_message_callback=callback, auto_ack=False)
            channel.start_consuming()
        except Exception:
            logger.exception("El consumidor se reconectara",
                             extra={"action": "recovery_attempted", "result": "retry", "correlation_id": None})
            if broker is not None and broker.is_open: broker.close()
            time.sleep(5)


if __name__ == "__main__": run()

import json
import logging
import time

from pydantic import ValidationError

from app.broker import PARKING_QUEUE, RETRY_DELAYS, connection, declare_topology, publish_retry
from app.database import SessionLocal
from app.logging_config import configure_logging, log_event
from app.parking_client import ParkingClient
from app.parking_processing import process_parking_event
from app.schemas import ParkingEventEnvelope


configure_logging("reservas-parking")
logger = logging.getLogger("reservas.parking")


def run() -> None:
    parking_client = ParkingClient()
    while True:
        broker = None
        try:
            broker = connection()
            channel = broker.channel()
            declare_topology(channel)
            channel.confirm_delivery()
            channel.basic_qos(prefetch_count=1)

            def callback(ch, method, properties, body):
                try:
                    envelope = ParkingEventEnvelope.model_validate(json.loads(body.decode("utf-8")))
                    with SessionLocal() as db:
                        result = process_parking_event(db, envelope, parking_client)
                        db.commit()
                    log_event(logger, "event_processed", result.status,
                              correlation_id=str(envelope.correlation_id),
                              event_id=str(envelope.event_id), reservation_id=result.reservation_id,
                              reservation_status=result.reservation_status)
                    ch.basic_ack(method.delivery_tag)
                except (json.JSONDecodeError, UnicodeDecodeError, ValidationError, ValueError):
                    logger.exception("Evento de parking invalido enviado a DLQ",
                                     extra={"action": "event_failed", "result": "dlq",
                                            "correlation_id": properties.correlation_id})
                    ch.basic_reject(method.delivery_tag, requeue=False)
                except Exception:
                    attempt = int((properties.headers or {}).get("x-retry-count", 0))
                    if attempt >= len(RETRY_DELAYS):
                        logger.exception("Evento de parking agoto reintentos",
                                         extra={"action": "event_failed", "result": "dlq",
                                                "correlation_id": properties.correlation_id})
                        ch.basic_reject(method.delivery_tag, requeue=False)
                    else:
                        publish_retry(ch, body, properties, attempt)
                        ch.basic_ack(method.delivery_tag)

            channel.basic_consume(queue=PARKING_QUEUE, on_message_callback=callback, auto_ack=False)
            channel.start_consuming()
        except Exception:
            logger.exception("El consumidor de parking se reconectara",
                             extra={"action": "recovery_attempted", "result": "retry",
                                    "correlation_id": None})
            if broker is not None and broker.is_open:
                broker.close()
            time.sleep(5)


if __name__ == "__main__":
    run()

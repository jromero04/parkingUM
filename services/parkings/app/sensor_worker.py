import json
import logging
import threading
import time

import pika
from pydantic import ValidationError

from app.broker import SENSOR_QUEUE, connection, declare_topology
from app.database import SessionLocal
from app.logging_config import configure_logging, log_event
from app.schemas import EventEnvelope
from app.sensor_processing import UnknownSensorError, mark_expired_sensors, process_sensor_event


configure_logging("parkings-sensors")
logger = logging.getLogger("parkings.sensors")
RETRY_DELAYS = (5, 15, 60)


def stale_loop() -> None:
    while True:
        try:
            with SessionLocal() as db:
                changed = mark_expired_sensors(db)
                db.commit()
                if changed:
                    log_event(
                        logger,
                        "sensor_stale",
                        "success",
                        level=logging.WARNING,
                        changed_count=changed,
                    )
        except Exception:
            logger.exception(
                "Fallo el verificador de vigencia",
                extra={"action": "event_failed", "result": "error", "correlation_id": None},
            )
        time.sleep(2)


def run() -> None:
    threading.Thread(target=stale_loop, daemon=True).start()
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
                    envelope = EventEnvelope.model_validate(json.loads(body.decode("utf-8")))
                    with SessionLocal() as db:
                        result = process_sensor_event(db, envelope)
                        db.commit()
                    action = {
                        "duplicate": "event_duplicate",
                        "discarded": "event_discarded",
                    }.get(result.status, "event_processed")
                    if result.event_type == "parking.sensor_recovered.v1":
                        action = "sensor_recovered"
                    level = logging.WARNING if result.status == "discarded" else logging.INFO
                    log_event(
                        logger,
                        action,
                        result.status,
                        level=level,
                        correlation_id=str(envelope.correlation_id),
                        event_id=str(envelope.event_id),
                        sensor_id=str(envelope.data.sensor_id),
                        spot_id=str(envelope.data.spot_id),
                        event_type=result.event_type,
                    )
                    ch.basic_ack(method.delivery_tag)
                except (json.JSONDecodeError, UnicodeDecodeError, ValidationError, UnknownSensorError, ValueError):
                    logger.exception(
                        "Evento de sensor invalido enviado a DLQ",
                        extra={"action": "event_failed", "result": "dlq", "correlation_id": None},
                    )
                    ch.basic_reject(method.delivery_tag, requeue=False)
                except Exception:
                    headers = dict(properties.headers or {})
                    attempt = int(headers.get("x-retry-count", 0))
                    logger.exception(
                        "Fallo transitorio procesando sensor",
                        extra={
                            "action": "event_failed",
                            "result": "retry" if attempt < len(RETRY_DELAYS) else "dlq",
                            "correlation_id": properties.correlation_id,
                            "event_id": properties.message_id,
                            "attempt": attempt + 1,
                        },
                    )
                    if attempt >= len(RETRY_DELAYS):
                        ch.basic_reject(method.delivery_tag, requeue=False)
                        return
                    delay = RETRY_DELAYS[attempt]
                    headers["x-retry-count"] = attempt + 1
                    ch.basic_publish(
                        exchange="",
                        routing_key=f"{SENSOR_QUEUE}.retry.{delay}",
                        body=body,
                        mandatory=True,
                        properties=pika.BasicProperties(
                            content_type=properties.content_type,
                            delivery_mode=2,
                            message_id=properties.message_id,
                            correlation_id=properties.correlation_id,
                            type=properties.type,
                            headers=headers,
                        ),
                    )
                    ch.basic_ack(method.delivery_tag)

            channel.basic_consume(queue=SENSOR_QUEUE, on_message_callback=callback, auto_ack=False)
            channel.start_consuming()
        except Exception:
            logger.exception(
                "El consumidor de sensores se reconectara",
                extra={"action": "recovery_attempted", "result": "retry", "correlation_id": None},
            )
            if broker is not None and broker.is_open:
                broker.close()
            time.sleep(5)


if __name__ == "__main__":
    run()

import json
import logging
import threading
import time

import pika
from pydantic import ValidationError

from app.broker import SENSOR_QUEUE, connection, declare_topology
from app.database import SessionLocal
from app.schemas import EventEnvelope
from app.sensor_processing import UnknownSensorError, mark_expired_sensors, process_sensor_event


logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("parkings.sensors")
RETRY_DELAYS = (5, 15, 60)


def stale_loop() -> None:
    while True:
        try:
            with SessionLocal() as db:
                changed = mark_expired_sensors(db)
                db.commit()
                if changed:
                    logger.warning("Sensores marcados stale: %s", changed)
        except Exception:
            logger.exception("Fallo el verificador de vigencia")
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
                    logger.info("Evento de sensor %s: %s", envelope.event_id, result)
                    ch.basic_ack(method.delivery_tag)
                except (json.JSONDecodeError, UnicodeDecodeError, ValidationError, UnknownSensorError, ValueError):
                    logger.exception("Evento de sensor invalido enviado a DLQ")
                    ch.basic_reject(method.delivery_tag, requeue=False)
                except Exception:
                    logger.exception("Fallo transitorio procesando sensor")
                    headers = dict(properties.headers or {})
                    attempt = int(headers.get("x-retry-count", 0))
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
            logger.exception("El consumidor de sensores se reconectara")
            if broker is not None and broker.is_open:
                broker.close()
            time.sleep(5)


if __name__ == "__main__":
    run()

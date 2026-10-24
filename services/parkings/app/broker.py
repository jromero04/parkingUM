import os

import pika


RABBITMQ_URL = os.getenv("RABBITMQ_URL", "amqp://guest:guest@rabbitmq:5672/%2F")
SENSOR_EXCHANGE = "sensors.events"
PARKING_EXCHANGE = "parking.events"
DLX = "system.dlx"
RETRY_EXCHANGE = "system.retry"
SENSOR_QUEUE = "parkings.sensor.q"
METRICS_QUEUE = "metricas.parking.q"
PARKING_EVENT_TYPES = (
    "parking.spot_initialized.v1",
    "parking.availability_changed.v1",
    "parking.sensor_stale.v1",
    "parking.sensor_recovered.v1",
    "parking.sensor_refreshed.v1",
)


def connection() -> pika.BlockingConnection:
    return pika.BlockingConnection(pika.URLParameters(RABBITMQ_URL))


def declare_topology(channel) -> None:
    channel.exchange_declare(exchange=SENSOR_EXCHANGE, exchange_type="topic", durable=True)
    channel.exchange_declare(exchange=PARKING_EXCHANGE, exchange_type="topic", durable=True)
    channel.exchange_declare(exchange=DLX, exchange_type="direct", durable=True)
    channel.exchange_declare(exchange=RETRY_EXCHANGE, exchange_type="direct", durable=True)
    channel.queue_declare(queue=f"{SENSOR_QUEUE}.dlq", durable=True)
    channel.queue_bind(queue=f"{SENSOR_QUEUE}.dlq", exchange=DLX, routing_key=SENSOR_QUEUE)
    channel.queue_declare(
        queue=SENSOR_QUEUE,
        durable=True,
        arguments={"x-dead-letter-exchange": DLX, "x-dead-letter-routing-key": SENSOR_QUEUE},
    )
    channel.queue_bind(queue=SENSOR_QUEUE, exchange=SENSOR_EXCHANGE, routing_key="sensor.reported.v1")
    channel.queue_bind(queue=SENSOR_QUEUE, exchange=RETRY_EXCHANGE, routing_key=SENSOR_QUEUE)
    for seconds in (5, 15, 60):
        channel.queue_declare(
            queue=f"{SENSOR_QUEUE}.retry.{seconds}",
            durable=True,
            arguments={
                "x-message-ttl": seconds * 1000,
                "x-dead-letter-exchange": RETRY_EXCHANGE,
                "x-dead-letter-routing-key": SENSOR_QUEUE,
            },
        )
    channel.queue_declare(queue=f"{METRICS_QUEUE}.dlq", durable=True)
    channel.queue_bind(queue=f"{METRICS_QUEUE}.dlq", exchange=DLX, routing_key=METRICS_QUEUE)
    channel.queue_declare(
        queue=METRICS_QUEUE,
        durable=True,
        arguments={"x-dead-letter-exchange": DLX, "x-dead-letter-routing-key": METRICS_QUEUE},
    )
    for event_type in PARKING_EVENT_TYPES:
        channel.queue_bind(queue=METRICS_QUEUE, exchange=PARKING_EXCHANGE, routing_key=event_type)

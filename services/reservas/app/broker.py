import pika

from app.config import get_settings


RESERVATIONS_EXCHANGE = "reservations.events"
PARKING_EXCHANGE = "parking.events"
DLX = "system.dlx"
RETRY_EXCHANGE = "system.retry"
PARKING_QUEUE = "reservas.parking.q"
METRICS_QUEUE = "metricas.reservas.q"
NOTIFICATIONS_QUEUE = "notificaciones.reservas.q"
LIFECYCLE_EVENT_TYPES = ("reservation.created.v1", "reservation.occupied.v1", "reservation.used.v1", "reservation.cancelled.v1")
NOTIFICATION_EVENT_TYPES = ("reservation.created.v1", "reservation.cancelled.v1")
RETRY_DELAYS = (5, 15, 60)


def connection() -> pika.BlockingConnection:
    return pika.BlockingConnection(pika.URLParameters(get_settings().rabbitmq_url))


def declare_topology(channel) -> None:
    channel.exchange_declare(exchange=RESERVATIONS_EXCHANGE, exchange_type="topic", durable=True)
    channel.exchange_declare(exchange=PARKING_EXCHANGE, exchange_type="topic", durable=True)
    channel.exchange_declare(exchange=DLX, exchange_type="direct", durable=True)
    channel.exchange_declare(exchange=RETRY_EXCHANGE, exchange_type="direct", durable=True)
    for queue, event_types in (
        (METRICS_QUEUE, LIFECYCLE_EVENT_TYPES),
        (NOTIFICATIONS_QUEUE, NOTIFICATION_EVENT_TYPES),
    ):
        channel.queue_declare(queue=f"{queue}.dlq", durable=True)
        channel.queue_bind(queue=f"{queue}.dlq", exchange=DLX, routing_key=queue)
        channel.queue_declare(
            queue=queue,
            durable=True,
            arguments={"x-dead-letter-exchange": DLX, "x-dead-letter-routing-key": queue},
        )
        for event_type in event_types:
            channel.queue_bind(queue=queue, exchange=RESERVATIONS_EXCHANGE, routing_key=event_type)
    channel.queue_declare(queue=f"{PARKING_QUEUE}.dlq", durable=True)
    channel.queue_bind(queue=f"{PARKING_QUEUE}.dlq", exchange=DLX, routing_key=PARKING_QUEUE)
    channel.queue_declare(
        queue=PARKING_QUEUE,
        durable=True,
        arguments={"x-dead-letter-exchange": DLX, "x-dead-letter-routing-key": PARKING_QUEUE},
    )
    channel.queue_bind(queue=PARKING_QUEUE, exchange=PARKING_EXCHANGE,
                       routing_key="parking.availability_changed.v1")
    channel.queue_bind(queue=PARKING_QUEUE, exchange=RETRY_EXCHANGE, routing_key=PARKING_QUEUE)
    for seconds in RETRY_DELAYS:
        channel.queue_declare(
            queue=f"{PARKING_QUEUE}.retry.{seconds}",
            durable=True,
            arguments={
                "x-message-ttl": seconds * 1000,
                "x-dead-letter-exchange": RETRY_EXCHANGE,
                "x-dead-letter-routing-key": PARKING_QUEUE,
            },
        )


def publish_retry(channel, body: bytes, properties, attempt: int) -> None:
    delay = RETRY_DELAYS[attempt]
    headers = dict(properties.headers or {})
    headers["x-retry-count"] = attempt + 1
    channel.basic_publish(
        exchange="", routing_key=f"{PARKING_QUEUE}.retry.{delay}", body=body, mandatory=True,
        properties=pika.BasicProperties(
            content_type=properties.content_type, delivery_mode=2, message_id=properties.message_id,
            correlation_id=properties.correlation_id, type=properties.type, headers=headers,
        ),
    )

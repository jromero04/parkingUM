import pika

from app.config import get_settings


PARKING_EXCHANGE = "parking.events"
RESERVATIONS_EXCHANGE = "reservations.events"
DLX = "system.dlx"
RETRY_EXCHANGE = "system.retry"
PARKING_QUEUE = "metricas.parking.q"
RESERVATIONS_QUEUE = "metricas.reservas.q"
PARKING_EVENTS = (
    "parking.spot_initialized.v1", "parking.availability_changed.v1", "parking.sensor_stale.v1",
    "parking.sensor_recovered.v1", "parking.sensor_refreshed.v1",
)
RESERVATION_EVENTS = ("reservation.created.v1", "reservation.cancelled.v1")
RETRY_DELAYS = (5, 15, 60)


def connection() -> pika.BlockingConnection:
    return pika.BlockingConnection(pika.URLParameters(get_settings().rabbitmq_url))


def declare_topology(channel) -> None:
    channel.exchange_declare(exchange=PARKING_EXCHANGE, exchange_type="topic", durable=True)
    channel.exchange_declare(exchange=RESERVATIONS_EXCHANGE, exchange_type="topic", durable=True)
    channel.exchange_declare(exchange=DLX, exchange_type="direct", durable=True)
    channel.exchange_declare(exchange=RETRY_EXCHANGE, exchange_type="direct", durable=True)
    for queue, exchange, event_types in (
        (PARKING_QUEUE, PARKING_EXCHANGE, PARKING_EVENTS),
        (RESERVATIONS_QUEUE, RESERVATIONS_EXCHANGE, RESERVATION_EVENTS),
    ):
        channel.queue_declare(queue=f"{queue}.dlq", durable=True)
        channel.queue_bind(queue=f"{queue}.dlq", exchange=DLX, routing_key=queue)
        channel.queue_declare(queue=queue, durable=True,
                              arguments={"x-dead-letter-exchange": DLX, "x-dead-letter-routing-key": queue})
        for event_type in event_types:
            channel.queue_bind(queue=queue, exchange=exchange, routing_key=event_type)
        channel.queue_bind(queue=queue, exchange=RETRY_EXCHANGE, routing_key=queue)
        for seconds in RETRY_DELAYS:
            retry_queue = f"{queue}.retry.{seconds}"
            channel.queue_declare(queue=retry_queue, durable=True, arguments={
                "x-message-ttl": seconds * 1000,
                "x-dead-letter-exchange": RETRY_EXCHANGE,
                "x-dead-letter-routing-key": queue,
            })


def publish_retry(channel, queue: str, body: bytes, properties, attempt: int) -> None:
    delay = RETRY_DELAYS[attempt]
    headers = dict(properties.headers or {})
    headers["x-retry-count"] = attempt + 1
    channel.basic_publish(
        exchange="", routing_key=f"{queue}.retry.{delay}", body=body, mandatory=True,
        properties=pika.BasicProperties(
            content_type=properties.content_type, delivery_mode=2, message_id=properties.message_id,
            correlation_id=properties.correlation_id, type=properties.type, headers=headers,
        ),
    )

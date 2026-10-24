import pika

from app.config import get_settings


RESERVATIONS_EXCHANGE = "reservations.events"
DLX = "system.dlx"
CONSUMER_QUEUES = ("metricas.reservas.q", "notificaciones.reservas.q")
EVENT_TYPES = ("reservation.created.v1", "reservation.cancelled.v1")


def connection() -> pika.BlockingConnection:
    return pika.BlockingConnection(pika.URLParameters(get_settings().rabbitmq_url))


def declare_topology(channel) -> None:
    channel.exchange_declare(exchange=RESERVATIONS_EXCHANGE, exchange_type="topic", durable=True)
    channel.exchange_declare(exchange=DLX, exchange_type="direct", durable=True)
    for queue in CONSUMER_QUEUES:
        channel.queue_declare(queue=f"{queue}.dlq", durable=True)
        channel.queue_bind(queue=f"{queue}.dlq", exchange=DLX, routing_key=queue)
        channel.queue_declare(
            queue=queue,
            durable=True,
            arguments={"x-dead-letter-exchange": DLX, "x-dead-letter-routing-key": queue},
        )
        for event_type in EVENT_TYPES:
            channel.queue_bind(queue=queue, exchange=RESERVATIONS_EXCHANGE, routing_key=event_type)

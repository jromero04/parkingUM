import pika

from app.config import get_settings


EXCHANGE = "reservations.events"
DLX = "system.dlx"
RETRY_EXCHANGE = "system.retry"
QUEUE = "notificaciones.reservas.q"
EVENTS = ("reservation.created.v1", "reservation.cancelled.v1")
RETRY_DELAYS = (5, 15, 60)


def connection():
    return pika.BlockingConnection(pika.URLParameters(get_settings().rabbitmq_url))


def declare_topology(channel) -> None:
    channel.exchange_declare(exchange=EXCHANGE, exchange_type="topic", durable=True)
    channel.exchange_declare(exchange=DLX, exchange_type="direct", durable=True)
    channel.exchange_declare(exchange=RETRY_EXCHANGE, exchange_type="direct", durable=True)
    channel.queue_declare(queue=f"{QUEUE}.dlq", durable=True)
    channel.queue_bind(queue=f"{QUEUE}.dlq", exchange=DLX, routing_key=QUEUE)
    channel.queue_declare(queue=QUEUE, durable=True,
                          arguments={"x-dead-letter-exchange": DLX, "x-dead-letter-routing-key": QUEUE})
    for event_type in EVENTS:
        channel.queue_bind(queue=QUEUE, exchange=EXCHANGE, routing_key=event_type)
    channel.queue_bind(queue=QUEUE, exchange=RETRY_EXCHANGE, routing_key=QUEUE)
    for seconds in RETRY_DELAYS:
        channel.queue_declare(queue=f"{QUEUE}.retry.{seconds}", durable=True, arguments={
            "x-message-ttl": seconds * 1000, "x-dead-letter-exchange": RETRY_EXCHANGE,
            "x-dead-letter-routing-key": QUEUE,
        })


def retry(channel, body, properties, attempt: int) -> None:
    headers = dict(properties.headers or {})
    headers["x-retry-count"] = attempt + 1
    channel.basic_publish(exchange="", routing_key=f"{QUEUE}.retry.{RETRY_DELAYS[attempt]}", body=body,
                          mandatory=True, properties=pika.BasicProperties(
                              content_type=properties.content_type, delivery_mode=2,
                              message_id=properties.message_id, correlation_id=properties.correlation_id,
                              type=properties.type, headers=headers))

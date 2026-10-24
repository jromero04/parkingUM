import argparse
import json
import uuid
from datetime import datetime, timezone

import pika
from sqlalchemy import select

from app.broker import SENSOR_EXCHANGE, connection, declare_topology
from app.database import SessionLocal
from app.models import Spot


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Publica un reporte de sensor válido para pruebas operativas.")
    parser.add_argument("--spot-id", default="22222222-2222-4222-8222-222222222222")
    parser.add_argument("--occupied", choices=("true", "false"), default="false")
    parser.add_argument("--sequence", type=int)
    parser.add_argument("--sensor-id")
    parser.add_argument("--unknown-sensor", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.sequence is not None and args.sensor_id is not None:
        sequence = args.sequence
        sensor_id = args.sensor_id
    else:
        with SessionLocal() as db:
            spot = db.scalar(select(Spot).where(Spot.id == args.spot_id))
            if spot is None:
                raise SystemExit(f"Plaza inexistente: {args.spot_id}")
            sequence = args.sequence or (spot.last_sequence or 0) + 1
            sensor_id = args.sensor_id or spot.sensor_id
    if args.unknown_sensor:
        sensor_id = str(uuid.uuid4())

    now = datetime.now(timezone.utc)
    event_id = str(uuid.uuid4())
    correlation_id = str(uuid.uuid4())
    event = {
        "event_id": event_id,
        "event_type": "sensor.reported.v1",
        "schema_version": 1,
        "occurred_at": now.isoformat(),
        "producer": "sensor-test-publisher",
        "correlation_id": correlation_id,
        "data": {
            "sensor_id": sensor_id,
            "spot_id": args.spot_id,
            "sequence": sequence,
            "observed_at": now.isoformat(),
            "physical_occupied": args.occupied == "true",
        },
    }

    broker = connection()
    try:
        channel = broker.channel()
        declare_topology(channel)
        channel.confirm_delivery()
        channel.basic_publish(
            exchange=SENSOR_EXCHANGE,
            routing_key="sensor.reported.v1",
            body=json.dumps(event).encode("utf-8"),
            mandatory=True,
            properties=pika.BasicProperties(
                content_type="application/json",
                delivery_mode=2,
                message_id=event_id,
                correlation_id=correlation_id,
                type="sensor.reported.v1",
            ),
        )
    finally:
        broker.close()
    print(json.dumps(event))


if __name__ == "__main__":
    main()

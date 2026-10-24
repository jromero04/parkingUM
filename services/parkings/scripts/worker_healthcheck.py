from sqlalchemy import text

from app.broker import connection
from app.database import SessionLocal


def main() -> None:
    with SessionLocal() as db:
        db.execute(text("SELECT 1"))
    broker = connection()
    try:
        if not broker.is_open:
            raise RuntimeError("RabbitMQ connection is not open")
    finally:
        broker.close()


if __name__ == "__main__":
    main()

import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ["DATABASE_URL"] = "sqlite+pysqlite:///:memory:"

from app.database import Base  # noqa: E402
from app.schemas import EventEnvelope, Recipient  # noqa: E402

USER_ID = str(uuid4())
RESERVATION_ID = str(uuid4())
PARKING_ID = str(uuid4())
SPOT_ID = str(uuid4())


@pytest.fixture
def db_session():
    engine = create_engine("sqlite+pysqlite:///:memory:", connect_args={"check_same_thread": False},
                           poolclass=StaticPool)
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, expire_on_commit=False)()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(engine)


class FakeRecipients:
    def __init__(self):
        self.calls = []

    def get(self, user_id, correlation_id):
        self.calls.append((user_id, correlation_id))
        return Recipient(user_id=user_id, email="hidden@example.com", name="Hidden")


def event(version=2, status="confirmed", ever=True, event_id=None):
    now = datetime.now(timezone.utc).isoformat()
    return EventEnvelope.model_validate({
        "event_id": event_id or str(uuid4()),
        "event_type": "reservation.created.v1" if status == "confirmed" else "reservation.cancelled.v1",
        "schema_version": 1, "occurred_at": now, "producer": "reservas", "correlation_id": str(uuid4()),
        "data": {"reservation": {
            "id": RESERVATION_ID, "user_id": USER_ID, "parking_id": PARKING_ID, "spot_id": SPOT_ID,
            "status": status, "ever_confirmed": ever, "created_at": now, "updated_at": now,
            "confirmed_at": now if ever else None, "cancelled_at": now if status == "cancelled" else None,
            "failure_code": None, "version": version,
        }},
    })

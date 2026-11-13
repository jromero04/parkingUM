import os
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
KEY_DIR = Path(tempfile.mkdtemp(prefix="metricas-test-keys-"))
private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
(KEY_DIR / "private.pem").write_bytes(private_key.private_bytes(
    serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()
))
(KEY_DIR / "public.pem").write_bytes(private_key.public_key().public_bytes(
    serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
))
os.environ["DATABASE_URL"] = "sqlite+pysqlite:///:memory:"
os.environ["JWT_PUBLIC_KEY_PATH"] = str(KEY_DIR / "public.pem")
os.environ["JWT_ISSUER"] = "parking-users"
os.environ["JWT_AUDIENCE"] = "parking-api"

from app.database import Base, get_db  # noqa: E402
from app.main import app  # noqa: E402


PARKING_ID = str(uuid4())
SPOT_ID = str(uuid4())
SENSOR_ID = str(uuid4())
RESERVATION_ID = str(uuid4())
USER_ID = str(uuid4())


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


@pytest.fixture
def client(db_session):
    def override_db():
        yield db_session
    app.dependency_overrides[get_db] = override_db
    with TestClient(app) as value:
        yield value
    app.dependency_overrides.clear()


def token(role="admin"):
    now = datetime.now(timezone.utc)
    return jwt.encode({"sub": USER_ID, "role": role, "iss": "parking-users", "aud": "parking-api",
                       "iat": now, "exp": now + timedelta(hours=1)},
                      (KEY_DIR / "private.pem").read_text(), algorithm="RS256")


@pytest.fixture
def admin_headers():
    return {"Authorization": f"Bearer {token()}"}


@pytest.fixture
def user_headers():
    return {"Authorization": f"Bearer {token('user')}"}


def parking_event(version=1, availability="unknown", occupied=None, assigned=None, event_id=None,
                  status="stale", expires_at=None, spot_id=SPOT_ID, parking_id=PARKING_ID,
                  sensor_id=SENSOR_ID, label="A-01"):
    now = datetime.now(timezone.utc)
    return {
        "event_id": event_id or str(uuid4()), "event_type": "parking.spot_initialized.v1",
        "schema_version": 1, "occurred_at": now.isoformat(), "producer": "parkings",
        "correlation_id": str(uuid4()), "data": {"reason": "test", "spot": {
            "id": spot_id, "parking_id": parking_id, "sensor_id": sensor_id, "label": label,
            "physical_occupied": occupied, "assigned_reservation_id": assigned,
            "sensor_status": status, "last_report_at": now.isoformat() if occupied is not None else None,
            "sensor_expires_at": expires_at.isoformat() if expires_at else None,
            "availability": availability, "version": version, "updated_at": now.isoformat(),
        }},
    }


def reservation_event(version=2, status="confirmed", ever_confirmed=True, event_id=None,
                      reservation_id=RESERVATION_ID, spot_id=SPOT_ID, parking_id=PARKING_ID,
                      used_at=None):
    now = used_at or datetime.now(timezone.utc)
    event_type = {
        "cancelled": "reservation.cancelled.v1",
        "occupied": "reservation.occupied.v1",
        "used": "reservation.used.v1",
    }.get(status, "reservation.created.v1")
    return {
        "event_id": event_id or str(uuid4()),
        "event_type": event_type,
        "schema_version": 1, "occurred_at": now.isoformat(), "producer": "reservas",
        "correlation_id": str(uuid4()), "data": {"reservation": {
            "id": reservation_id, "user_id": USER_ID, "parking_id": parking_id, "spot_id": spot_id,
            "status": status, "ever_confirmed": ever_confirmed, "created_at": now.isoformat(),
            "updated_at": now.isoformat(), "confirmed_at": now.isoformat() if ever_confirmed else None,
            "occupied_at": now.isoformat() if status in {"occupied", "used"} else None,
            "used_at": now.isoformat() if status == "used" else None,
            "cancelled_at": now.isoformat() if status == "cancelled" else None,
            "failure_code": None, "version": version,
        }},
    }

import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool


SERVICE_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SERVICE_ROOT))

TEST_KEYS = SERVICE_ROOT / ".test-keys"
TEST_KEYS.mkdir(exist_ok=True)
private_path = TEST_KEYS / "private.pem"
public_path = TEST_KEYS / "public.pem"
if not private_path.exists():
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_path.write_bytes(
        key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption())
    )
    public_path.write_bytes(
        key.public_key().public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)
    )

os.environ["DATABASE_URL"] = "sqlite+pysqlite:///:memory:"
os.environ["JWT_PUBLIC_KEY_PATH"] = str(public_path)
os.environ["RESERVATIONS_SERVICE_TOKEN"] = "test-reservations-token"
os.environ["SENSOR_FRESH_SECONDS"] = "15"

from app.config import get_settings  # noqa: E402

get_settings.cache_clear()

from app.database import Base, get_db  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Parking, Spot  # noqa: E402


PARKING_ID = "11111111-1111-4111-8111-111111111111"
SPOT_ID = "22222222-2222-4222-8222-222222222222"
SENSOR_ID = "33333333-3333-4333-8333-333333333333"


@pytest.fixture
def db_session():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSession = sessionmaker(bind=engine, expire_on_commit=False)
    Base.metadata.create_all(engine)
    with TestingSession() as session:
        session.add(Parking(id=PARKING_ID, name="Parking Central", address="Av. Dra. María Luisa de Saldún Rodríguez 2037"))
        session.add(
            Spot(
                id=SPOT_ID,
                parking_id=PARKING_ID,
                sensor_id=SENSOR_ID,
                label="A-01",
                physical_occupied=False,
                sensor_status="fresh",
                last_sequence=1,
                last_report_at=datetime.now(timezone.utc),
                sensor_expires_at=datetime.now(timezone.utc) + timedelta(minutes=1),
            )
        )
        session.commit()
        yield session
    Base.metadata.drop_all(engine)


@pytest.fixture
def client(db_session):
    def override_db():
        yield db_session

    app.dependency_overrides[get_db] = override_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def headers_for_role():
    def build(role: str) -> dict[str, str]:
        now = datetime.now(timezone.utc)
        token = jwt.encode(
            {
                "sub": "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
                "role": role,
                "iss": "parking-users",
                "aud": "parking-api",
                "iat": now,
                "exp": now + timedelta(minutes=5),
            },
            private_path.read_text(encoding="utf-8"),
            algorithm="RS256",
        )
        return {"Authorization": f"Bearer {token}"}
    return build


@pytest.fixture
def auth_headers(headers_for_role):
    return headers_for_role("user")


@pytest.fixture
def service_headers():
    return {"X-Service-Token": "test-reservations-token"}

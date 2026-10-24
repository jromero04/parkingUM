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
KEY_DIR = Path(tempfile.mkdtemp(prefix="reservas-test-keys-"))
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
from app.parking_client import ParkingResult, get_parking_client  # noqa: E402


USER_ID = str(uuid4())
OTHER_USER_ID = str(uuid4())
PARKING_ID = str(uuid4())
SPOT_ID = str(uuid4())


class FakeParkingClient:
    def __init__(self):
        self.assign_results = [ParkingResult("assigned", 201)]
        self.release_results = [ParkingResult("released", 200)]
        self.assign_calls = []
        self.release_calls = []

    def assign(self, *args):
        self.assign_calls.append(args)
        return self.assign_results.pop(0)

    def release(self, *args):
        self.release_calls.append(args)
        return self.release_results.pop(0)


@pytest.fixture
def db_session():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, expire_on_commit=False)()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(engine)


@pytest.fixture
def fake_parkings():
    return FakeParkingClient()


@pytest.fixture
def client(db_session, fake_parkings):
    def override_db():
        yield db_session

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_parking_client] = lambda: fake_parkings
    with TestClient(app) as value:
        yield value
    app.dependency_overrides.clear()


def token_for(user_id: str) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user_id, "role": "user", "iss": "parking-users", "aud": "parking-api",
        "iat": now, "exp": now + timedelta(hours=1),
    }
    return jwt.encode(payload, (KEY_DIR / "private.pem").read_text(), algorithm="RS256")


@pytest.fixture
def auth_headers():
    return {"Authorization": f"Bearer {token_for(USER_ID)}"}


@pytest.fixture
def other_auth_headers():
    return {"Authorization": f"Bearer {token_for(OTHER_USER_ID)}"}


@pytest.fixture
def create_payload():
    return {"parking_id": PARKING_ID, "spot_id": SPOT_ID}

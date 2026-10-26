from datetime import datetime, timedelta, timezone
from uuid import uuid4

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient

from app.config import get_settings
from app.fleet import sensor_states
from app.main import app


@pytest.fixture
def api(tmp_path, monkeypatch):
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_path = tmp_path / "private.pem"
    public_path = tmp_path / "public.pem"
    private_path.write_bytes(key.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
    public_path.write_bytes(key.public_key().public_bytes(
        serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo))
    monkeypatch.setenv("STATE_DB_PATH", str(tmp_path / "sensors.db"))
    monkeypatch.setenv("JWT_PUBLIC_KEY_PATH", str(public_path))
    monkeypatch.setenv("START_PUBLISHER", "false")
    get_settings.cache_clear()
    sensor_states.cache_clear()

    def headers(role: str) -> dict[str, str]:
        now = datetime.now(timezone.utc)
        token = jwt.encode({"sub": str(uuid4()), "role": role, "iss": "parking-users",
                            "aud": "parking-api", "iat": now, "exp": now + timedelta(minutes=5)},
                           private_path.read_text(encoding="utf-8"), algorithm="RS256")
        return {"Authorization": f"Bearer {token}"}

    with TestClient(app) as client:
        yield client, headers
    get_settings.cache_clear()
    sensor_states.cache_clear()


def test_simulation_requires_admin(api):
    client, headers = api
    assert client.get("/api/v1/simulacion/sensores").status_code == 401
    response = client.get("/api/v1/simulacion/sensores", headers=headers("user"))
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "FORBIDDEN"


def test_admin_can_stop_and_recover_one_sensor(api):
    client, headers = api
    admin = headers("admin")
    listed = client.get("/api/v1/simulacion/sensores", headers=admin)
    assert listed.status_code == 200
    assert len(listed.json()) == 168
    assert listed.json()[0]["label"] == "A-01"

    stopped = client.put("/api/v1/simulacion/sensores/C-12", json={"failed": True}, headers=admin)
    assert stopped.status_code == 200
    assert stopped.json()["status"] == "stopped"
    assert stopped.json()["label"] == "C-12"
    assert sum(item["status"] == "stopped" for item in client.get(
        "/api/v1/simulacion/sensores", headers=admin).json()) == 1

    recovered = client.put("/api/v1/simulacion/sensores/C-12", json={"failed": False}, headers=admin)
    assert recovered.status_code == 200
    assert recovered.json()["status"] == "active"

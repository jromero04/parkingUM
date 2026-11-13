from datetime import datetime, timedelta, timezone
from uuid import uuid4

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient

from app.config import get_settings
from app.fleet import sensor_definitions, sensor_states
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


def test_simulation_requires_sensor_role(api):
    client, headers = api
    assert client.get("/api/v1/simulacion/sensores").status_code == 401
    response = client.get("/api/v1/simulacion/sensores", headers=headers("user"))
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "FORBIDDEN"
    assert client.get("/api/v1/simulacion/sensores", headers=headers("admin")).status_code == 403


def test_sensor_user_can_stop_and_recover_one_sensor(api):
    client, headers = api
    sensor_user = headers("sensor")
    listed = client.get("/api/v1/simulacion/sensores", headers=sensor_user)
    assert listed.status_code == 200
    assert len(listed.json()) == 168
    assert listed.json()[0]["label"] == "A-01"

    stopped = client.put("/api/v1/simulacion/sensores/C-12", json={"failed": True}, headers=sensor_user)
    assert stopped.status_code == 200
    assert stopped.json()["status"] == "stopped"
    assert stopped.json()["label"] == "C-12"
    assert sum(item["status"] == "stopped" for item in client.get(
        "/api/v1/simulacion/sensores", headers=sensor_user).json()) == 1

    recovered = client.put("/api/v1/simulacion/sensores/C-12", json={"failed": False}, headers=sensor_user)
    assert recovered.status_code == 200
    assert recovered.json()["status"] == "active"


def test_sensor_user_can_simulate_vehicle_occupancy(api):
    client, headers = api
    sensor_user = headers("sensor")

    occupied = client.put(
        "/api/v1/simulacion/sensores/C-12/occupancy",
        json={"occupied": True},
        headers=sensor_user,
    )
    assert occupied.status_code == 200
    assert occupied.json()["label"] == "C-12"
    assert occupied.json()["physical_occupied"] is True

    sensor = next(item for item in client.get(
        "/api/v1/simulacion/sensores", headers=sensor_user).json() if item["label"] == "C-12")
    assert sensor["physical_occupied"] is True
    state = next(state for definition, state in zip(sensor_definitions(), sensor_states())
                 if definition["label"] == "C-12")
    assert state.prepare_event()["data"]["physical_occupied"] is True

    released = client.put(
        "/api/v1/simulacion/sensores/C-12/occupancy",
        json={"occupied": False},
        headers=sensor_user,
    )
    assert released.status_code == 200
    assert released.json()["physical_occupied"] is False


def test_occupancy_simulation_requires_sensor_role(api):
    client, headers = api
    response = client.put(
        "/api/v1/simulacion/sensores/A-01/occupancy",
        json={"occupied": True},
        headers=headers("admin"),
    )
    assert response.status_code == 403

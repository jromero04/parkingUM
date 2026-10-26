from uuid import uuid4

from app.models import User
from app.security import hash_password


def register(client, email="ada@example.com"):
    return client.post(
        "/api/v1/usuarios/registro",
        json={"name": "Ada Lovelace", "email": email, "password": "una-clave-segura-123"},
        headers={"X-Correlation-ID": str(uuid4())},
    )


def test_register_login_and_me(client):
    created = register(client)
    assert created.status_code == 201
    assert created.json()["user"]["email"] == "ada@example.com"
    assert "password" not in created.text

    logged_in = client.post(
        "/api/v1/usuarios/login",
        json={"email": "ADA@example.com", "password": "una-clave-segura-123"},
    )
    assert logged_in.status_code == 200
    token = logged_in.json()["access_token"]

    current = client.get("/api/v1/usuarios/me", headers={"Authorization": f"Bearer {token}"})
    assert current.status_code == 200
    assert current.json()["id"] == created.json()["user"]["id"]


def test_duplicate_email_is_conflict(client):
    assert register(client).status_code == 201
    duplicate = register(client, "ADA@example.com")
    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["code"] == "EMAIL_ALREADY_EXISTS"


def test_validation_and_unknown_fields_use_contract_error(client):
    response = client.post(
        "/api/v1/usuarios/registro",
        json={"name": " Ada ", "email": "invalid", "password": "short", "role": "admin"},
    )
    assert response.status_code == 422
    body = response.json()
    assert body["error"]["code"] == "VALIDATION_ERROR"
    assert body["correlation_id"] == response.headers["X-Correlation-ID"]


def test_internal_recipient_requires_service_token(client):
    user_id = register(client).json()["user"]["id"]
    forbidden = client.get(f"/internal/v1/usuarios/{user_id}/destinatario")
    assert forbidden.status_code == 403

    allowed = client.get(
        f"/internal/v1/usuarios/{user_id}/destinatario",
        headers={"X-Service-Token": "test-notifications-token"},
    )
    assert allowed.status_code == 200
    assert allowed.json()["user_id"] == user_id


def test_me_rejects_invalid_token(client):
    response = client.get("/api/v1/usuarios/me", headers={"Authorization": "Bearer invalid"})
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHORIZED"


def test_seeded_sensor_role_can_log_in(client, db_session):
    db_session.add(User(
        name="Operador de sensores",
        email="sensores@example.com",
        password_hash=hash_password("una-clave-sensor-123"),
        role="sensor",
    ))
    db_session.commit()

    response = client.post(
        "/api/v1/usuarios/login",
        json={"email": "sensores@example.com", "password": "una-clave-sensor-123"},
    )

    assert response.status_code == 200
    assert response.json()["user"]["role"] == "sensor"


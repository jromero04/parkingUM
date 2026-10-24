import json
import os
import subprocess
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PROJECT = os.getenv("INTEGRATION_PROJECT", "estacionamiento-metrics-it")
GATEWAY = "http://127.0.0.1:18080"
COMPOSE = ["docker", "compose", "-p", PROJECT, "-f", "docker-compose.yml",
           "-f", "docker-compose.integration.yml"]
ENV = {**os.environ, "GATEWAY_PORT": "18080"}


def run(*args: str, check=True) -> str:
    result = subprocess.run([*COMPOSE, *args], cwd=ROOT, env=ENV, check=False, capture_output=True,
                            text=True, encoding="utf-8", errors="replace")
    if check and result.returncode:
        raise RuntimeError(f"Fallo docker compose {' '.join(args)}\n{result.stdout}\n{result.stderr}")
    return result.stdout.strip()


def request(method, url, body=None, headers=None):
    call = urllib.request.Request(url, method=method,
        data=json.dumps(body).encode() if body is not None else None,
        headers={"Content-Type": "application/json", **(headers or {})})
    try:
        with urllib.request.urlopen(call, timeout=15) as response:
            content = response.read().decode()
            return response.status, json.loads(content) if content else None
    except urllib.error.HTTPError as exc:
        content = exc.read().decode()
        return exc.code, json.loads(content) if content else None


def wait_until(predicate, message, timeout=45):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.5)
    raise AssertionError(message)


def login(email, password):
    status, body = request("POST", f"{GATEWAY}/api/v1/usuarios/login", {"email": email, "password": password})
    assert status == 200
    return {"Authorization": f"Bearer {body['access_token']}"}


def test_contract():
    admin = login("admin-integration@example.com", "integration-admin-password")
    email = f"metrics-{uuid.uuid4()}@example.com"
    assert request("POST", f"{GATEWAY}/api/v1/usuarios/registro",
                   {"name": "Metrics User", "email": email, "password": "integration-password-123"})[0] == 201
    user = login(email, "integration-password-123")
    assert request("GET", f"{GATEWAY}/api/v1/metricas/resumen", headers=user)[0] == 403

    def initial_projection():
        status, body = request("GET", f"{GATEWAY}/api/v1/metricas/resumen", headers=admin)
        return status == 200 and body["spots"]["total"] == 1
    wait_until(initial_projection, "Metricas no proyecto el seed")
    status, alerts = request("GET", f"{GATEWAY}/api/v1/metricas/alertas", headers=admin)
    assert status == 200 and len(alerts["items"]) == 1

    status, parkings = request("GET", f"{GATEWAY}/api/v1/parkings", headers=user)
    parking_id = parkings[0]["id"]
    status, spots = request("GET", f"{GATEWAY}/api/v1/parkings/{parking_id}/plazas", headers=user)
    spot_id = spots[0]["id"]
    run("exec", "-T", "parkings-sensor-worker", "python", "scripts/publish_sensor_event.py",
        "--occupied", "false")

    def available():
        status, body = request("GET", f"{GATEWAY}/api/v1/metricas/resumen", headers=admin)
        return status == 200 and body["spots"]["available"] == 1
    wait_until(available, "Metricas no proyecto la plaza disponible")

    key = str(uuid.uuid4())
    status, created = request("POST", f"{GATEWAY}/api/v1/reservas",
        {"parking_id": parking_id, "spot_id": spot_id}, {**user, "Idempotency-Key": key})
    assert status == 201
    reservation_id = created["reservation"]["id"]

    def reserved():
        status, body = request("GET", f"{GATEWAY}/api/v1/metricas/resumen", headers=admin)
        return status == 200 and body["spots"]["reserved"] == 1 \
            and body["reservations"]["confirmed_current"] == 1 \
            and body["reservations"]["created_total"] == 1
    wait_until(reserved, "Metricas no proyecto la reserva confirmada")

    status, _ = request("POST", f"{GATEWAY}/api/v1/reservas/{reservation_id}/cancelacion",
                        headers={**user, "Idempotency-Key": str(uuid.uuid4())})
    assert status == 200

    def cancelled():
        status, body = request("GET", f"{GATEWAY}/api/v1/metricas/resumen", headers=admin)
        return status == 200 and body["spots"]["available"] == 1 \
            and body["reservations"] == {"confirmed_current": 0, "created_total": 1, "cancelled_total": 1}
    wait_until(cancelled, "Metricas no proyecto la cancelacion")


def main():
    print(f"Levantando pila aislada {PROJECT}...")
    run("down", "-v", "--remove-orphans", check=False)
    try:
        run("up", "--build", "-d", "--wait")
        test_contract()
        print("OK: integracion de Metricas, proyecciones, RBAC, alertas y eventos desordenables")
    finally:
        run("down", "-v", "--remove-orphans", check=False)


if __name__ == "__main__":
    main()

import json
import os
import subprocess
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PROJECT = os.getenv("INTEGRATION_PROJECT", "estacionamiento-reservations-it")
GATEWAY = "http://127.0.0.1:18080"
COMPOSE = [
    "docker", "compose", "-p", PROJECT,
    "-f", "docker-compose.yml", "-f", "docker-compose.integration.yml",
]
ENV = {**os.environ, "GATEWAY_PORT": "18080", "SENSOR_SIMULATOR_ENABLED": "false"}


def run(*args: str, check: bool = True) -> str:
    result = subprocess.run(
        [*COMPOSE, *args], cwd=ROOT, env=ENV, check=False, capture_output=True,
        text=True, encoding="utf-8", errors="replace",
    )
    if check and result.returncode != 0:
        raise RuntimeError(
            f"Fallo docker compose {' '.join(args)}\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
        )
    return result.stdout.strip()


def request(method: str, url: str, body=None, headers=None):
    data = json.dumps(body).encode() if body is not None else None
    call = urllib.request.Request(
        url, data=data, method=method,
        headers={"Content-Type": "application/json", **(headers or {})},
    )
    try:
        with urllib.request.urlopen(call, timeout=15) as response:
            content = response.read().decode()
            response_headers = {key.lower(): value for key, value in response.headers.items()}
            return response.status, json.loads(content) if content else None, response_headers
    except urllib.error.HTTPError as exc:
        content = exc.read().decode()
        response_headers = {key.lower(): value for key, value in exc.headers.items()}
        return exc.code, json.loads(content) if content else None, response_headers


def wait_until(predicate, message: str, timeout: float = 45) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.5)
    raise AssertionError(message)


def queue_messages(queue: str) -> int:
    output = run("exec", "-T", "rabbitmq", "rabbitmqctl", "-q", "list_queues", "name", "messages")
    for line in output.splitlines():
        fields = line.split()
        if len(fields) == 2 and fields[0] == queue:
            return int(fields[1])
    return 0


def register_and_login(label: str) -> dict[str, str]:
    email = f"reservas-it-{label}-{uuid.uuid4()}@example.com"
    status, _, _ = request(
        "POST", f"{GATEWAY}/api/v1/usuarios/registro",
        {"name": f"Reservas {label}", "email": email, "password": "integration-password-123"},
    )
    assert status == 201
    status, login, _ = request(
        "POST", f"{GATEWAY}/api/v1/usuarios/login",
        {"email": email, "password": "integration-password-123"},
    )
    assert status == 200
    return {"Authorization": f"Bearer {login['access_token']}"}


def publish_free_sensor() -> None:
    run(
        "exec", "-T", "parkings-sensor-worker", "python", "scripts/publish_sensor_event.py",
        "--occupied", "false",
    )


def test_contract() -> None:
    auth = register_and_login("Owner")
    other_auth = register_and_login("Other")
    status, parkings, _ = request("GET", f"{GATEWAY}/api/v1/parkings", headers=auth)
    assert status == 200 and len(parkings) == 1
    parking_id = parkings[0]["id"]
    status, spots, _ = request("GET", f"{GATEWAY}/api/v1/parkings/{parking_id}/plazas", headers=auth)
    assert status == 200 and len(spots) == 1
    spot_id = spots[0]["id"]
    publish_free_sensor()

    def is_available() -> bool:
        status, values, _ = request("GET", f"{GATEWAY}/api/v1/parkings/{parking_id}/plazas", headers=auth)
        return status == 200 and values[0]["availability"] == "available"

    wait_until(is_available, "El sensor no volvio disponible la plaza")
    key = str(uuid.uuid4())
    payload = {"parking_id": parking_id, "spot_id": spot_id}
    status, created, headers = request(
        "POST", f"{GATEWAY}/api/v1/reservas", payload,
        {**auth, "Idempotency-Key": key, "X-Correlation-ID": str(uuid.uuid4())},
    )
    assert status == 201 and created["reservation"]["status"] == "confirmed"
    reservation_id = created["reservation"]["id"]
    assert headers["location"].endswith(reservation_id)

    status, repeated, _ = request(
        "POST", f"{GATEWAY}/api/v1/reservas", payload, {**auth, "Idempotency-Key": key},
    )
    assert status == 201 and repeated == created
    status, conflict, _ = request(
        "POST", f"{GATEWAY}/api/v1/reservas",
        {"parking_id": parking_id, "spot_id": str(uuid.uuid4())},
        {**auth, "Idempotency-Key": key},
    )
    assert status == 409 and conflict["error"]["code"] == "IDEMPOTENCY_KEY_REUSED"
    status, listing, _ = request("GET", f"{GATEWAY}/api/v1/reservas?status=confirmed", headers=auth)
    assert status == 200 and listing["items"][0]["id"] == reservation_id
    assert request("GET", f"{GATEWAY}/api/v1/reservas/{reservation_id}", headers=other_auth)[0] == 404
    assert request("GET", f"{GATEWAY}/internal/v1/asignaciones/{reservation_id}")[0] == 404

    run("stop", "parkings")
    cancel_key = str(uuid.uuid4())
    status, pending, headers = request(
        "POST", f"{GATEWAY}/api/v1/reservas/{reservation_id}/cancelacion",
        headers={**auth, "Idempotency-Key": cancel_key},
    )
    assert status == 202 and pending["reservation"]["status"] == "cancel_pending"
    assert headers["retry-after"] == "2"
    run("start", "parkings")

    def was_cancelled() -> bool:
        status, value, _ = request("GET", f"{GATEWAY}/api/v1/reservas/{reservation_id}", headers=auth)
        return status == 200 and value["status"] == "cancelled"

    wait_until(was_cancelled, "El worker no recupero la cancelacion", timeout=60)
    status, cancelled_replay, _ = request(
        "POST", f"{GATEWAY}/api/v1/reservas/{reservation_id}/cancelacion",
        headers={**auth, "Idempotency-Key": cancel_key},
    )
    assert status == 200 and cancelled_replay["reservation"]["status"] == "cancelled"
    wait_until(lambda: queue_messages("metricas.reservas.q") >= 2,
               "Metricas no recibio los eventos de reserva")
    assert queue_messages("notificaciones.reservas.q") >= 2


def main() -> None:
    print(f"Levantando pila aislada {PROJECT}...")
    run("down", "-v", "--remove-orphans", check=False)
    try:
        run("up", "--build", "-d", "--wait")
        test_contract()
        print("OK: integracion de Reservas, idempotencia, recuperacion, outbox, Gateway y ownership")
    finally:
        if os.getenv("KEEP_INTEGRATION_STACK") != "1":
            run("down", "-v", "--remove-orphans", check=False)


if __name__ == "__main__":
    main()

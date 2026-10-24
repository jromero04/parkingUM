import concurrent.futures
import json
import os
import subprocess
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PROJECT = os.getenv("INTEGRATION_PROJECT", "estacionamiento-parking-it")
GATEWAY = "http://127.0.0.1:18080"
PARKINGS = "http://127.0.0.1:18001"
COMPOSE = [
    "docker",
    "compose",
    "-p",
    PROJECT,
    "-f",
    "docker-compose.yml",
    "-f",
    "docker-compose.integration.yml",
]
ENV = {**os.environ, "GATEWAY_PORT": "18080"}


def run(*args: str, check: bool = True) -> str:
    result = subprocess.run(
        [*COMPOSE, *args],
        cwd=ROOT,
        env=ENV,
        check=False,
        capture_output=True,
        text=True,
    )
    if check and result.returncode != 0:
        raise RuntimeError(
            f"Falló docker compose {' '.join(args)}\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
        )
    return result.stdout.strip()


def request(method: str, url: str, body=None, headers=None):
    data = json.dumps(body).encode() if body is not None else None
    all_headers = {"Content-Type": "application/json", **(headers or {})}
    call = urllib.request.Request(url, data=data, headers=all_headers, method=method)
    try:
        with urllib.request.urlopen(call, timeout=10) as response:
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


def publish_sensor(
    *,
    occupied: bool,
    unknown_sensor: bool = False,
    sequence: int | None = None,
    sensor_id: str | None = None,
) -> None:
    command = [
        "exec",
        "-T",
        "parkings-sensor-worker",
        "python",
        "scripts/publish_sensor_event.py",
        "--occupied",
        str(occupied).lower(),
    ]
    if unknown_sensor:
        command.append("--unknown-sensor")
    if sequence is not None:
        command.extend(["--sequence", str(sequence)])
    if sensor_id is not None:
        command.extend(["--sensor-id", sensor_id])
    run(*command)


def db_scalar(expression: str) -> int:
    program = (
        "from sqlalchemy import text; from app.database import SessionLocal; "
        f"db=SessionLocal(); print(db.scalar(text({expression!r}))); db.close()"
    )
    output = run("exec", "-T", "parkings", "python", "-c", program)
    return int(output.splitlines()[-1])


def queue_messages(queue: str) -> int:
    output = run("exec", "-T", "rabbitmq", "rabbitmqctl", "-q", "list_queues", "name", "messages")
    for line in output.splitlines():
        fields = line.split()
        if len(fields) == 2 and fields[0] == queue:
            return int(fields[1])
    return 0


def worker_is_healthy(service: str) -> bool:
    container_id = run("ps", "-q", service)
    if not container_id:
        return False
    result = subprocess.run(
        ["docker", "inspect", "--format", "{{.State.Health.Status}}", container_id],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip() == "healthy"


def assignment_request(reservation_id: str, operation_id: str, parking_id: str, spot_id: str):
    return request(
        "PUT",
        f"{PARKINGS}/internal/v1/asignaciones/{reservation_id}",
        {"parking_id": parking_id, "spot_id": spot_id, "operation_id": operation_id},
        {"X-Service-Token": "integration-reservations-token", "X-Correlation-ID": str(uuid.uuid4())},
    )


def test_contract() -> None:
    correlation_id = str(uuid.uuid4())
    email = f"parking-it-{uuid.uuid4()}@example.com"
    status, _, _ = request(
        "POST",
        f"{GATEWAY}/api/v1/usuarios/registro",
        {"name": "Parking Integration", "email": email, "password": "integration-password-123"},
        {"X-Correlation-ID": correlation_id},
    )
    assert status == 201
    status, login, _ = request(
        "POST",
        f"{GATEWAY}/api/v1/usuarios/login",
        {"email": email, "password": "integration-password-123"},
    )
    assert status == 200
    auth = {"Authorization": f"Bearer {login['access_token']}"}

    status, parkings, headers = request("GET", f"{GATEWAY}/api/v1/parkings", headers=auth)
    assert status == 200 and len(parkings) == 1
    generated = uuid.UUID(headers["x-correlation-id"])
    assert generated.version == 4 and generated.variant == uuid.RFC_4122
    parking_id = parkings[0]["id"]

    status, spots, _ = request("GET", f"{GATEWAY}/api/v1/parkings/{parking_id}/plazas", headers=auth)
    assert status == 200 and spots[0]["availability"] == "unknown"
    spot_id = spots[0]["id"]
    sensor_id = spots[0]["sensor_id"]

    status, _, _ = request("GET", f"{GATEWAY}/internal/v1/asignaciones/{uuid.uuid4()}")
    assert status == 404
    status, _, _ = request(
        "PUT",
        f"{PARKINGS}/internal/v1/asignaciones/{uuid.uuid4()}",
        {"parking_id": parking_id, "spot_id": spot_id, "operation_id": str(uuid.uuid4())},
    )
    assert status == 403

    publish_sensor(occupied=False)

    def available() -> bool:
        status, values, _ = request("GET", f"{GATEWAY}/api/v1/parkings/{parking_id}/plazas", headers=auth)
        return status == 200 and values[0]["availability"] == "available"

    wait_until(available, "El reporte de sensor no volvió disponible la plaza")

    first = (str(uuid.uuid4()), str(uuid.uuid4()))
    second = (str(uuid.uuid4()), str(uuid.uuid4()))
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        futures = [
            pool.submit(assignment_request, first[0], first[1], parking_id, spot_id),
            pool.submit(assignment_request, second[0], second[1], parking_id, spot_id),
        ]
        responses = [future.result() for future in futures]
    assert sorted(response[0] for response in responses) == [201, 409]
    winner = first if responses[0][0] == 201 else second
    assert assignment_request(winner[0], winner[1], parking_id, spot_id)[0] == 200

    release_key = str(uuid.uuid4())
    status, released, _ = request(
        "DELETE",
        f"{PARKINGS}/internal/v1/asignaciones/{winner[0]}",
        headers={"X-Service-Token": "integration-reservations-token", "Idempotency-Key": release_key},
    )
    assert status == 200 and released["status"] == "released"

    closed_id = str(uuid.uuid4())
    status, _, _ = request(
        "DELETE",
        f"{PARKINGS}/internal/v1/asignaciones/{closed_id}",
        headers={"X-Service-Token": "integration-reservations-token", "Idempotency-Key": str(uuid.uuid4())},
    )
    assert status == 200
    assert assignment_request(closed_id, str(uuid.uuid4()), parking_id, spot_id)[0] == 409

    run("stop", "rabbitmq")
    broker_outage = (str(uuid.uuid4()), str(uuid.uuid4()))
    assert assignment_request(broker_outage[0], broker_outage[1], parking_id, spot_id)[0] == 201
    assert db_scalar("SELECT count(*) FROM outbox_events WHERE published_at IS NULL") >= 1
    run("start", "rabbitmq")
    wait_until(
        lambda: db_scalar("SELECT count(*) FROM outbox_events WHERE published_at IS NULL") == 0,
        "El outbox no se recuperó después de reiniciar RabbitMQ",
        timeout=60,
    )

    request(
        "DELETE",
        f"{PARKINGS}/internal/v1/asignaciones/{broker_outage[0]}",
        headers={"X-Service-Token": "integration-reservations-token", "Idempotency-Key": str(uuid.uuid4())},
    )
    publish_sensor(occupied=False)
    publish_sensor(occupied=False, unknown_sensor=True)
    wait_until(
        lambda: queue_messages("parkings.sensor.q.dlq") >= 1,
        "El evento inválido no llegó a la DLQ",
    )
    assert queue_messages("metricas.parking.q") >= 1

    retry_sequence = db_scalar("SELECT COALESCE(last_sequence, 0) + 100 FROM spots LIMIT 1")
    run("stop", "parkings-db")
    publish_sensor(occupied=False, sequence=retry_sequence, sensor_id=sensor_id)
    wait_until(
        lambda: sum(queue_messages(f"parkings.sensor.q.retry.{seconds}") for seconds in (5, 15, 60)) >= 1,
        "El fallo transitorio no fue enviado a una cola de reintento",
        timeout=10,
    )
    run("start", "parkings-db")

    def retry_was_processed() -> bool:
        try:
            return db_scalar("SELECT COALESCE(last_sequence, 0) FROM spots LIMIT 1") == retry_sequence
        except (RuntimeError, ValueError):
            return False

    wait_until(retry_was_processed, "El evento no fue procesado después del reintento", timeout=45)
    wait_until(lambda: worker_is_healthy("parkings-sensor-worker"), "Sensor worker no está healthy")
    wait_until(lambda: worker_is_healthy("parkings-outbox-worker"), "Outbox worker no está healthy")


def main() -> None:
    print(f"Levantando pila aislada {PROJECT}...")
    run("down", "-v", "--remove-orphans", check=False)
    try:
        run("up", "--build", "-d", "--wait")
        test_contract()
        print("OK: integración de Parkings, PostgreSQL, RabbitMQ, Gateway, outbox, reintentos y DLQ")
    finally:
        if os.getenv("KEEP_INTEGRATION_STACK") != "1":
            run("down", "-v", "--remove-orphans", check=False)


if __name__ == "__main__":
    main()

import json
import os
import subprocess
import urllib.request
import uuid
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PROJECT = os.getenv("INTEGRATION_PROJECT", "estacionamiento-frontend-it")
GATEWAY = "http://127.0.0.1:18080"
COMPOSE = [
    "docker", "compose", "-p", PROJECT,
    "-f", "docker-compose.yml", "-f", "docker-compose.integration.yml",
]
ENV = {**os.environ, "GATEWAY_PORT": "18080", "SENSOR_SIMULATOR_ENABLED": "true"}


def run(*args: str, check: bool = True) -> str:
    result = subprocess.run(
        [*COMPOSE, *args], cwd=ROOT, env=ENV, check=False,
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    if check and result.returncode:
        raise RuntimeError(f"Falló docker compose {' '.join(args)}\n{result.stdout}\n{result.stderr}")
    return result.stdout.strip()


def post(path: str, body: dict) -> tuple[int, dict]:
    request = urllib.request.Request(
        f"{GATEWAY}{path}", method="POST",
        data=json.dumps(body).encode(), headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=15) as response:
        return response.status, json.loads(response.read().decode())


def test_public_edge() -> None:
    with urllib.request.urlopen(GATEWAY, timeout=15) as response:
        page = response.read().decode()
        assert response.status == 200
        assert "Parking SD" in page

    with urllib.request.urlopen(f"{GATEWAY}/login", timeout=15) as response:
        assert response.status == 200
        assert "Bienvenido" in response.read().decode()

    email = f"frontend-{uuid.uuid4()}@example.com"
    password = "integration-password-123"
    status, _ = post("/api/v1/usuarios/registro", {
        "name": "Frontend User", "email": email, "password": password,
    })
    assert status == 201
    status, login = post("/api/v1/usuarios/login", {"email": email, "password": password})
    assert status == 200 and login["access_token"]


def main() -> None:
    print(f"Levantando pila aislada {PROJECT}...")
    run("down", "-v", "--remove-orphans", check=False)
    try:
        run("up", "--build", "-d", "--wait")
        test_public_edge()
        print("OK: frontend servido por Gateway y flujo de autenticación disponible")
    finally:
        if os.getenv("KEEP_INTEGRATION_STACK") != "1":
            run("down", "-v", "--remove-orphans", check=False)


if __name__ == "__main__":
    main()

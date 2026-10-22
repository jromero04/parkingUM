# Estacionamiento inteligente

Implementacion inicial del proyecto de Sistemas Distribuidos. El repositorio sigue los contratos de `Contratos_SD_v1.md` y el diseno de `Entrega SD - Informe.pdf`.

## Primer incremento

Este punto de partida incluye:

- servicio **Usuarios** con registro, login, consulta del usuario autenticado y consulta interna de destinatario;
- contrasenas con Argon2id y access tokens JWT RS256;
- errores uniformes y propagacion de `X-Correlation-ID`;
- PostgreSQL administrado mediante una migracion Alembic;
- API Gateway NGINX que conserva `/api/v1` y no publica rutas internas;
- Docker Compose y pruebas automatizadas del flujo principal.

Los servicios Parkings, Reservas, Metricas, Notificaciones, el simulador y el frontend se incorporaran en incrementos posteriores. No se agregaron implementaciones vacias que aparenten garantias distribuidas todavia inexistentes.

## Ejecutar

Requisitos: Docker y Docker Compose.

```powershell
Copy-Item .env.example .env
docker compose up --build
```

Para crear el administrador inicial, complete `ADMIN_NAME`, `ADMIN_EMAIL` y `ADMIN_PASSWORD` en `.env` antes del primer arranque. El registro publico nunca acepta el rol.

La API queda disponible a traves del Gateway en `http://localhost:8080/api/v1/usuarios`. La documentacion OpenAPI del servicio puede habilitarse directamente en desarrollo publicando su puerto, pero no se expone en el Gateway.

Ejemplo de registro:

```powershell
$headers = @{ 'Content-Type' = 'application/json'; 'X-Correlation-ID' = [guid]::NewGuid().ToString() }
$body = @{ name = 'Ada Lovelace'; email = 'ada@example.com'; password = 'una-clave-segura-123' } | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri http://localhost:8080/api/v1/usuarios/registro -Headers $headers -Body $body
```

## Pruebas locales

```powershell
python -m venv .venv
.\.venv\Scripts\pip install -r services\usuarios\requirements-dev.txt
.\.venv\Scripts\pytest
```

Las pruebas usan SQLite solo como doble local de persistencia. La ejecucion del prototipo usa PostgreSQL.


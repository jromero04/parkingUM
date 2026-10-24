# Estacionamiento inteligente

Implementacion inicial del proyecto de Sistemas Distribuidos. El repositorio sigue los contratos de `Contratos_SD_v1.md` y el diseno de `Entrega SD - Informe.pdf`.

## Incrementos implementados

Este punto de partida incluye:

- servicio **Usuarios** con registro, login, consulta del usuario autenticado y consulta interna de destinatario;
- contrasenas con Argon2id y access tokens JWT RS256;
- errores uniformes y propagacion de `X-Correlation-ID`;
- PostgreSQL administrado mediante una migracion Alembic;
- API Gateway NGINX que conserva `/api/v1` y no publica rutas internas;
- Docker Compose y pruebas automatizadas del flujo principal.
- servicio **Parkings** con consultas autenticadas, asignaciones internas idempotentes y liberacion segura;
- plazas con estado fisico, asignacion y vigencia de sensor independientes;
- consumo durable de reportes de sensor, reintentos/DLQ y outbox transaccional para eventos de Parkings;
- base, migracion y seed reproducible propios de Parkings.
- servicio **Reservas** con creación, consulta, listado y cancelación autenticadas;
- idempotencia persistente por usuario, coordinación recuperable con Parkings y estados pending/cancel_pending;
- outbox transaccional y publicación durable de eventos de reservas para Métricas y Notificaciones.

Los servicios Metricas, Notificaciones, el simulador y el frontend se incorporaran en incrementos posteriores. No se agregaron implementaciones vacias que aparenten garantias distribuidas todavia inexistentes.

## Ejecutar

Requisitos: Docker y Docker Compose.

```powershell
Copy-Item .env.example .env
docker compose up --build
```

Para crear el administrador inicial, complete `ADMIN_NAME`, `ADMIN_EMAIL` y `ADMIN_PASSWORD` en `.env` antes del primer arranque. El registro publico nunca acepta el rol.

La API queda disponible a traves del Gateway en `http://localhost:8080/api/v1/usuarios`. La documentacion OpenAPI del servicio puede habilitarse directamente en desarrollo publicando su puerto, pero no se expone en el Gateway.

Los estacionamientos y sus plazas se consultan en `http://localhost:8080/api/v1/parkings` usando un access token emitido por Usuarios. El seed crea `Parking Central` y la plaza `A-01`, inicialmente con disponibilidad `unknown` hasta recibir un reporte vigente del sensor.

Las reservas se crean en `http://localhost:8080/api/v1/reservas` con el mismo access token y una cabecera `Idempotency-Key` UUID. Si Parkings no puede resolver la operación de inmediato, la API responde 202 y el worker de recuperación continúa usando los mismos identificadores estables.

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
.\.venv\Scripts\pip install -r services\parkings\requirements-dev.txt
.\.venv\Scripts\pytest
.\.venv\Scripts\pytest services\parkings\tests
.\.venv\Scripts\pytest services\reservas\tests
```

Las suites se ejecutan por servicio porque cada contenedor mantiene su propio paquete `app`. Las pruebas usan SQLite solo como doble local de persistencia. La ejecucion del prototipo usa PostgreSQL.

La suite de Parkings también puede ejecutarse en una imagen reproducible con Python 3.13:

```powershell
docker build --target test -t proyecto-sd-parkings-test services/parkings
docker run --rm proyecto-sd-parkings-test
```

La suite reproducible de Reservas se ejecuta con:

```powershell
docker build --target test -t proyecto-sd-reservas-test services/reservas
docker run --rm proyecto-sd-reservas-test
```

La prueba integral levanta un proyecto Compose aislado en los puertos 18080 y 18001. Comprueba PostgreSQL real, concurrencia de asignaciones, RabbitMQ, outbox, recuperación del broker, reintentos, DLQ, Gateway y healthchecks; al finalizar elimina sus contenedores y volúmenes de prueba:

```powershell
python scripts\test_parking_integration.py
```

La integración de Reservas valida el flujo HTTP completo, ownership, idempotencia, recuperación tras una caída de Parkings y publicación de outbox:

```powershell
python scripts\test_reservations_integration.py
```


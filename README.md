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
- servicio **Métricas** con proyecciones idempotentes de plazas y reservas, resumen administrativo y alertas stale;
- control de versiones para eventos duplicados o desordenados y consumidores RabbitMQ con reintentos/DLQ.
- servicio **Notificaciones** con entregas simuladas persistentes, resolución interna de destinatarios y supresión por versión;
- plantillas de confirmación/cancelación, deduplicación y reintentos/DLQ sin exponer emails en logs.
- simulador durable de **Sensores** con secuencia monotónica, estado físico configurable y publisher confirms;
- persistencia del evento pendiente para reintentar exactamente el mismo reporte tras una caída.
- **Frontend** responsive en Next.js con autenticación en memoria, consulta y reserva de plazas;
- seguimiento y cancelación de reservas, además de métricas y alertas para administradores.

El navegador accede a todas las funciones mediante el mismo Gateway; las rutas internas permanecen fuera de la red pública.

## Ejecutar

Requisitos: Docker y Docker Compose.

```powershell
Copy-Item .env.example .env
docker compose up --build
```

Para crear el administrador inicial, complete `ADMIN_NAME`, `ADMIN_EMAIL` y `ADMIN_PASSWORD` en `.env` antes del primer arranque. El registro publico nunca acepta el rol.

La interfaz queda disponible en `http://localhost:8080`. El access token se mantiene solo en memoria, por lo que recargar la página requiere iniciar sesión nuevamente, de acuerdo con el contrato v1.

La API queda disponible a traves del Gateway en `http://localhost:8080/api/v1/usuarios`. La documentacion OpenAPI del servicio puede habilitarse directamente en desarrollo publicando su puerto, pero no se expone en el Gateway.

Los estacionamientos y sus plazas se consultan en `http://localhost:8080/api/v1/parkings` usando un access token emitido por Usuarios. El seed crea `Parking Central` y la plaza `A-01`, inicialmente con disponibilidad `unknown` hasta recibir un reporte vigente del sensor.

Las reservas se crean en `http://localhost:8080/api/v1/reservas` con el mismo access token y una cabecera `Idempotency-Key` UUID. Si Parkings no puede resolver la operación de inmediato, la API responde 202 y el worker de recuperación continúa usando los mismos identificadores estables.

El resumen y las alertas se consultan en `http://localhost:8080/api/v1/metricas/resumen` y `/api/v1/metricas/alertas`. Ambos endpoints requieren un access token con rol `admin`.

Ejemplo de registro:

```powershell
$headers = @{ 'Content-Type' = 'application/json'; 'X-Correlation-ID' = [guid]::NewGuid().ToString() }
$body = @{ name = 'Ada Lovelace'; email = 'ada@example.com'; password = 'una-clave-segura-123' } | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri http://localhost:8080/api/v1/usuarios/registro -Headers $headers -Body $body
```

## Pruebas locales

El frontend usa Node.js 22 o superior:

```powershell
cd frontend
npm install
npm test
npm run lint
npm run build
```

La integración del frontend valida la imagen de producción, su publicación mediante NGINX y el flujo de registro/login:

```powershell
python scripts\test_frontend_integration.py
```

```powershell
python -m venv .venv
.\.venv\Scripts\pip install -r services\usuarios\requirements-dev.txt
.\.venv\Scripts\pip install -r services\parkings\requirements-dev.txt
.\.venv\Scripts\pytest
.\.venv\Scripts\pytest services\parkings\tests
.\.venv\Scripts\pytest services\reservas\tests
.\.venv\Scripts\pytest services\metricas\tests
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

La suite reproducible de Métricas se ejecuta con:

```powershell
docker build --target test -t proyecto-sd-metricas-test services/metricas
docker run --rm proyecto-sd-metricas-test
```

La suite reproducible de Notificaciones se ejecuta con:

```powershell
docker build --target test -t proyecto-sd-notificaciones-test services/notificaciones
docker run --rm proyecto-sd-notificaciones-test
```

La suite reproducible del simulador se ejecuta con:

```powershell
docker build --target test -t proyecto-sd-sensores-test services/sensores
docker run --rm proyecto-sd-sensores-test
```

Para cambiar el estado físico durante la demo:

```powershell
docker compose exec sensores python scripts/set_state.py --occupied true
docker compose exec sensores python scripts/set_state.py --occupied false
```

La integración del simulador valida publicación automática, cambio físico, reinicio y recuperación de RabbitMQ:

```powershell
python scripts\test_sensors_integration.py
```

La integración de Notificaciones valida destinatarios, las tres plantillas, persistencia y ausencia de emails en logs:

```powershell
python scripts\test_notifications_integration.py
```

La prueba integral levanta un proyecto Compose aislado en los puertos 18080 y 18001. Comprueba PostgreSQL real, concurrencia de asignaciones, RabbitMQ, outbox, recuperación del broker, reintentos, DLQ, Gateway y healthchecks; al finalizar elimina sus contenedores y volúmenes de prueba:

```powershell
python scripts\test_parking_integration.py
```

La integración de Reservas valida el flujo HTTP completo, ownership, idempotencia, recuperación tras una caída de Parkings y publicación de outbox:

```powershell
python scripts\test_reservations_integration.py
```

La integración de Métricas valida RBAC administrativo y la proyección completa seed → sensor → reserva → cancelación:

```powershell
python scripts\test_metrics_integration.py
```


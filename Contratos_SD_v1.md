# Contratos v1 — Estacionamiento inteligente

Fecha: 21 de octubre de 2026. Estado: propuesta de especificación para implementar en equipo.

Base: «Entrega SD - Informe.pdf». El informe fija servicios, tecnologías y reglas generales. Las rutas, campos, estados, tiempos, seguridad, outbox y mecanismos concretos de recuperación de este documento son decisiones propuestas para completar ese diseño; no describen código ya implementado. No incluye Pagos, reservas por horarios, hardware ni despliegue productivo.

## 1. Convenciones comunes

- API pública: `/api/v1`, a través de NGINX. API interna: `/internal/v1`, solo en la red privada de Docker, sin rutas públicas en NGINX.
- NGINX conserva el prefijo público al reenviar solicitudes; cada FastAPI expone las rutas completas de su servicio. No se hace una segunda reescritura de rutas.
- JSON UTF-8. Nombres de campos en `snake_case`; valores enumerados en inglés y minúsculas. Textos de interfaz traducidos en el frontend.
- Identificadores: UUID representados como cadenas. Los ejemplos abreviados de las tablas son nombres de campos, no UUID válidos.
- Fechas: RFC 3339 en UTC, con sufijo `Z`. Los contenedores del prototipo comparten un reloj de host sincronizado.
- `null` expresa ausencia; un campo obligatorio no se omite. Campos opcionales se indican expresamente. Los demás son obligatorios.
- `version` es un entero >= 1 que aumenta por cada cambio público de una entidad. Es una versión de entidad, distinta de `schema_version` del evento.
- Las entradas no aceptan campos desconocidos. Las salidas y eventos pueden incorporar campos opcionales compatibles: los clientes ignoran los que no conocen.
- Los GET de colecciones devuelven `{ "items": [...], "next_cursor": null }`. Query: `limit` de 1 a 100, por defecto 20; `cursor` opcional, opaco y generado por el servidor. Orden estable `(created_at, id)`, ascendente; para plazas `(parking_id, id)`. No se garantiza una fotografía transaccional entre páginas si hay cambios concurrentes.
- CORS permite únicamente el origen configurado del frontend. Ninguna credencial real se guarda en Git.

### 1.1 Cabeceras

| Cabecera | Uso |
|---|---|
| `Content-Type: application/json` | Solicitudes con cuerpo JSON y respuestas JSON |
| `Authorization: Bearer <access_token>` | Endpoints públicos protegidos |
| `X-Correlation-ID` | UUID. NGINX lo genera si falta o no es válido; lo conserva si es válido, lo propaga y lo devuelve |
| `Idempotency-Key` | UUID obligatorio para crear y cancelar reservas |
| `X-Service-Token` | Credencial interna del servicio llamador; nunca enviada por el navegador |

Si NGINX genera el identificador, debe producir un UUID en el formato acordado, sin asumir que el identificador nativo de NGINX ya cumple este formato. El cliente puede aportarlo para facilitar las pruebas.

### 1.2 Seguridad

- Usuarios emite JWT firmados con RS256. Clave privada solo en Usuarios; clave pública montada en los servicios que validan tokens. Para el prototipo la clave es estática por entorno.
- Claims: `sub` (UUID del usuario), `role` (`user`, `admin` o `sensor`), `iss` (`parking-users`), `aud` (`parking-api`), `iat`, `exp`. Duración propuesta: 60 minutos.
- Cada API protegida verifica firma, algoritmo fijo, emisor, audiencia y expiración; no confía en un `user_id` enviado por el navegador.
- Usuarios nuevos tienen `role=user`. El administrador y el operador de sensores se crean por seed/configuración. El registro no acepta un rol.
- No hay refresh token en v1. Cerrar sesión elimina el token del cliente; no lo revoca de inmediato en el servidor. El frontend lo mantiene en memoria y requiere nuevo login al recargar.
- Comunicación interna autenticada mediante secretos distintos por llamador y permisos por ruta, cargados por entorno. Reservas puede asignar/liberar/consultar asignaciones; Notificaciones puede resolver destinatarios. Se comparan los secretos sin registrarlos.
- NGINX elimina cualquier `X-Service-Token` aportado por un cliente público. Los endpoints internos siguen exigiendo su propia credencial y no se publican a través del Gateway.
- Contraseñas almacenadas con hash Argon2id. No se registran contraseñas, tokens, hashes ni cuerpos completos de login.
- El prototipo usa una red Docker privada para HTTP interno. Cualquier exposición externa requiere HTTPS; los secretos nunca se transmiten por Internet en HTTP.

### 1.3 Errores

Todos los servicios, incluidos errores de validación FastAPI y fallos de proxy NGINX, usan esta estructura:

```json
{
  "error": {
    "code": "SPOT_UNAVAILABLE",
    "message": "La plaza no está disponible.",
    "details": {"reason": "assigned"}
  },
  "correlation_id": "d2043f50-9d07-4ab2-869d-eec973844f75"
}
```

`details` es un objeto, vacío si no corresponde. Para validación: `details.fields` es una lista de `{field, reason}`. El frontend decide por `code`, no por el texto del mensaje.

| HTTP | Código | Significado |
|---|---|---|
| 400 | `INVALID_CURSOR`, `INVALID_IDEMPOTENCY_KEY` | Parámetro de control incorrecto o cabecera obligatoria ausente |
| 401 | `UNAUTHORIZED`, `INVALID_CREDENTIALS` | Token ausente/inválido o login incorrecto |
| 403 | `FORBIDDEN` | Rol o servicio sin permiso |
| 404 | `RESOURCE_NOT_FOUND` | Recurso inexistente o reserva ajena que no debe revelarse |
| 409 | `EMAIL_ALREADY_EXISTS` | Email registrado |
| 409 | `SPOT_UNAVAILABLE` | Plaza ocupada, asignada o sin datos vigentes |
| 409 | `IDEMPOTENCY_KEY_REUSED` | Misma clave con distinta operación o cuerpo |
| 409 | `ASSIGNMENT_CLOSED`, `RESERVATION_TERMINAL` | Operación cerrada o estado incompatible |
| 422 | `VALIDATION_ERROR` | Cuerpo o parámetros de negocio inválidos |
| 502 | `UPSTREAM_ERROR` | Error de comunicación del Gateway |
| 503 | `SERVICE_UNAVAILABLE` | Dependencia necesaria no disponible antes de aceptar la operación |
| 504 | `UPSTREAM_TIMEOUT` | Gateway agotó la espera; la operación puede haber sido aceptada |
| 500 | `INTERNAL_ERROR` | Fallo inesperado; no se exponen detalles internos |

Timeout HTTP interno propuesto: conexión 2 s, lectura 5 s. Presupuesto inicial de la API de Reservas: 8 s; timeout del Gateway: 12 s. Si una operación aceptada queda sin resultado dentro del presupuesto, Reservas devuelve 202. El cliente reintenta con la misma clave si pierde la respuesta completa. Estos tiempos son configurables y no prueban por sí solos que una operación haya fallado.

## 2. Datos y reglas del dominio

### 2.1 Objetos públicos

**User**: `id`, `name`, `email`, `role`, `created_at`. `name`: 1–100 caracteres sin espacios extremos; `email`: validado, normalizado a minúsculas y único; contraseña de registro: 12–128 caracteres. No se devuelve el hash.

**Parking**: `id`, `name`, `address`, `created_at`. `name`: 1–100 caracteres; `address`: 1–250.

**Spot**:

| Campo | Tipo y significado |
|---|---|
| `id`, `parking_id`, `sensor_id` | UUID; una plaza tiene un sensor en v1 |
| `label` | Texto, único dentro del parking |
| `physical_occupied` | Booleano o null si nunca hubo reporte aceptado |
| `assigned_reservation_id` | UUID o null |
| `sensor_status` | `fresh` o `stale`; nunca reportado implica stale |
| `last_report_at` | Fecha del reporte aceptado, o null |
| `sensor_expires_at` | Fecha límite de vigencia, o null |
| `availability` | `available`, `reserved`, `occupied` o `unknown` |
| `version` | Versión de la proyección de plaza |
| `updated_at` | Fecha del último cambio de la proyección |

La vigencia se calcula con la fecha de observación aceptada: `ahora < sensor_expires_at`. Al llegar al límite deja de estar vigente. La comprobación se hace en GET y en la operación atómica, aunque la tarea periódica todavía no haya publicado el cambio.

`availability` es una clasificación exclusiva para la interfaz, con esta prioridad:

1. Información stale o sin ocupación conocida → `unknown`.
2. Información fresh y físicamente ocupada → `occupied`.
3. Información fresh, físicamente libre y asignada → `reserved`.
4. Información fresh, físicamente libre y sin asignación → `available`.

Los campos originales se conservan: `unknown` no borra la reserva ni el último estado físico. Una plaza ocupada puede conservar una reserva. No hay finalización automática de reservas por eventos físicos en v1.

**Reservation**: `id`, `user_id`, `parking_id`, `spot_id`, `status`, `ever_confirmed`, `created_at`, `updated_at`, `confirmed_at` (fecha/null), `cancelled_at` (fecha/null), `failure_code` (string/null), `version`.

Estados: `pending`, `confirmed`, `cancel_pending`, `cancelled`, `rejected`. `ever_confirmed` comienza en false y solo puede pasar a true cuando Reservas confirma de forma persistente. Una asignación física pendiente de recuperación no equivale todavía a reserva confirmada.

No se limita a una reserva por usuario en v1. Cada plaza sí admite una sola asignación. No hay horarios, pago ni vencimiento automático de una reserva confirmada.

### 2.2 Autoridad sobre los datos

| Servicio | Datos que administra |
|---|---|
| Usuarios | Identidad, credenciales y roles |
| Parkings | Estacionamientos, plazas, sensores, ocupación, vigencia y registro de asignaciones |
| Reservas | Reservas, operaciones pendientes, claves de idempotencia y outbox |
| Métricas | Proyecciones de plazas/reservas y eventos procesados |
| Notificaciones | Registro persistente de entregas simuladas y eventos procesados |

Cada servicio accede exclusivamente a su base. Los UUID de otros servicios son referencias lógicas, sin claves foráneas entre bases. Para simplificar, pueden compartir una instancia PostgreSQL con bases y permisos separados. Se propone una base adicional de Notificaciones para que la deduplicación sobreviva reinicios y sea compartida por sus réplicas; es un detalle adicional al informe.

## 3. API pública

### 3.1 Usuarios

| Método y ruta | Acceso | Entrada | Respuesta |
|---|---|---|---|
| `POST /api/v1/usuarios/registro` | Público | `{name,email,password}` | 201 `{user: User}` |
| `POST /api/v1/usuarios/login` | Público | `{email,password}` | 200 `{access_token,token_type:"bearer",expires_in:3600,user:User}` |
| `GET /api/v1/usuarios/me` | Autenticado | Sin cuerpo | 200 `User` |

El registro repetido devuelve 409; no inicia sesión automáticamente. Login incorrecto devuelve un mensaje genérico. No se incluye edición de perfil ni administración de usuarios en v1.

### 3.2 Parkings

| Método y ruta | Acceso | Respuesta |
|---|---|---|
| `GET /api/v1/parkings` | Autenticado | 200 colección de `Parking` |
| `GET /api/v1/parkings/{parking_id}` | Autenticado | 200 `Parking` |
| `GET /api/v1/parkings/{parking_id}/plazas` | Autenticado | 200 colección de `Spot` |
| `GET /api/v1/parkings/{parking_id}/plazas/{spot_id}` | Autenticado | 200 `Spot` |

Listado de plazas admite filtro opcional `availability` con uno de los cuatro valores. Una plaza que no pertenece al parking devuelve 404. La disponibilidad es informativa: obtener `available` no garantiza que una solicitud posterior consiga asignarla.

Estacionamientos, plazas, sensores y admin se cargan con un seed reproducible. No se agregan endpoints CRUD administrativos para ellos en esta versión.

### 3.3 Reservas

| Método y ruta | Acceso | Entrada | Respuesta |
|---|---|---|---|
| `POST /api/v1/reservas` | Autenticado | `{parking_id,spot_id}` y `Idempotency-Key` | 201 `{reservation:Reservation}` si confirmed; 202 mismo cuerpo si pending; 409 error con `reservation_id` si rejected por conflicto |
| `GET /api/v1/reservas` | Autenticado | Filtro opcional `status` | 200 colección de reservas del usuario |
| `GET /api/v1/reservas/{reservation_id}` | Propietario | Sin cuerpo | 200 `Reservation` |
| `POST /api/v1/reservas/{reservation_id}/cancelacion` | Propietario | Sin cuerpo y `Idempotency-Key` | 200 `{reservation:Reservation}` si cancelled; 202 si cancel_pending |

No se acepta `user_id` en el cuerpo. En v1 admin tampoco obtiene acceso implícito a las reservas personales: el dashboard usa agregados de Métricas.

Para una creación rechazada por parking/plaza inexistente se devuelve 404 con `details.reservation_id` si se alcanzó a persistir la operación; para plaza no disponible, 409 con `details.reason` (`occupied`, `assigned`, `sensor_stale`) y `details.reservation_id`. Si la dependencia todavía no permite determinar el resultado, se conserva pending y se devuelve 202; no se rechaza por adivinar el resultado.

Las respuestas 201/202 incluyen `Location: /api/v1/reservas/{id}`. Las respuestas 202 incluyen `Retry-After: 2`. El frontend consulta la reserva cada 2 s mientras la pantalla esté abierta; después de 30 s puede mostrar «La operación continúa pendiente» y permitir volver a consultarla.

**Idempotencia pública:** la clave se identifica por `(user_id, Idempotency-Key)` y se guarda persistentemente, con ruta, método, cuerpo normalizado, ID de reserva y resultado. La misma clave y solicitud nunca crean otra reserva ni otra cancelación. Una clave reutilizada con datos/ruta distintos devuelve 409. Las operaciones terminales conservan su resultado inicial de operación; para conocer el estado actual de una reserva que luego se canceló se usa GET. Una repetición de una operación aún pendiente puede devolver su resultado actualizado. Las claves y resultados se retienen durante todo el prototipo.

Una cancelación con nueva clave sobre una reserva ya cancelled devuelve 200 sin repetir efectos. Sobre rejected devuelve 409 `RESERVATION_TERMINAL`. Se permite cancelar pending; pasa a cancel_pending y se resuelve con el cierre interno de asignación. No se permite reactivar una reserva cancelled o rejected.

### 3.4 Métricas y dashboard

`GET /api/v1/metricas/resumen?parking_id=<UUID opcional>` — solo admin.

```json
{
  "parking_id": null,
  "spots": {
    "total": 20,
    "available": 8,
    "reserved": 4,
    "occupied": 6,
    "unknown": 2,
    "assigned_total": 5,
    "physically_occupied_fresh": 6
  },
  "reservations": {
    "confirmed_current": 5,
    "created_total": 15,
    "cancelled_total": 10
  },
  "occupancy": {"occupied_fresh": 6, "fresh_total": 18, "percentage": 33.33},
  "last_projected_at": "2026-10-21T14:00:00Z",
  "computed_at": "2026-10-21T14:00:02Z",
  "consistency": "eventual"
}
```

Definiciones:

- `available + reserved + occupied + unknown = total` en una misma lectura de la proyección. Las dos últimas medidas auxiliares no se suman a esa partición.
- `assigned_total`: plazas con asignación, incluso ocupadas o stale.
- `confirmed_current`: reservas cuyo último estado proyectado es confirmed. Puede diferir temporalmente de las asignaciones de Parkings.
- `created_total`: reservas con `ever_confirmed=true`. `cancelled_total`: reservas cancelled y ever_confirmed=true. Ambas son acumuladas desde el inicio del prototipo, no por día.
- `percentage = 100 * occupied_fresh / fresh_total`, redondeado a 2 decimales; null si fresh_total es 0. No se considera libre una plaza sin información vigente.
- No se ofrece consistencia instantánea entre componentes. `last_projected_at` indica la última aplicación de un cambio, no acredita que la cola esté al día; puede ser null al inicio. `computed_at` es el momento de la consulta.

`GET /api/v1/metricas/alertas?parking_id=<UUID opcional>` — solo admin. Colección de alertas activas:

```json
{
  "items": [{
    "spot_id": "1c51fda6-45da-4db4-9a5b-94b4ce7b796a",
    "parking_id": "17b3ac82-2720-4823-b2fe-691fb216cf0d",
    "sensor_id": "63d6ab4a-ecda-4353-a907-28a93ebf1d88",
    "code": "SENSOR_DATA_STALE",
    "since": "2026-10-21T13:59:45Z",
    "last_report_at": "2026-10-21T13:59:30Z",
    "message": "No hay reportes vigentes del sensor."
  }],
  "next_cursor": null,
  "computed_at": "2026-10-21T14:00:02Z"
}
```

`last_report_at` puede ser null; para una plaza que nunca reportó, `since` es su alta. La alerta no afirma que el sensor esté desconectado. El dashboard consulta resumen y alertas cada 5 s; no se requiere WebSocket.

Si el servicio de Métricas no responde, la interfaz muestra error y la hora del último dato mostrado, sin presentar ese dato como actualizado. Un filtro de parking sin proyección devuelve 404; el seed debe publicar las instantáneas iniciales.

## 4. API interna y coordinación distribuida

### 4.1 Operaciones de Parkings para Reservas

| Método y ruta | Entrada | Resultado |
|---|---|---|
| `PUT /internal/v1/asignaciones/{reservation_id}` | `{parking_id,spot_id,operation_id}` | 201 primera asignación; 200 repetición de asignación exitosa |
| `GET /internal/v1/asignaciones/{reservation_id}` | Sin cuerpo | 200 registro existente; 404 si nunca hubo intento ni cierre |
| `DELETE /internal/v1/asignaciones/{reservation_id}` | Sin cuerpo; `Idempotency-Key` interno con UUID de cancelación estable | 200 registro con status released |

Registro de asignación: `{reservation_id,parking_id,spot_id,operation_id,status,reason,version,updated_at}`. `parking_id`, `spot_id`, `operation_id` pueden ser null en un cierre recibido antes que la creación. `reason` puede ser null. Estados: assigned, rejected, released.

- `operation_id` de asignación se genera una sola vez por reserva; no cambia al reintentar. Una repetición debe comprobar el registro persistido antes de reevaluar disponibilidad.
- Asignar ejecuta en una transacción local el registro de operación, la comprobación/actualización condicional de plaza y su outbox. No usa un lock solo en memoria como garantía.
- En éxito se guarda assigned. En rechazo definitivo se guarda rejected y se devuelve 409 `SPOT_UNAVAILABLE` o 404 según corresponda. Repetir no convierte un rechazo en asignación si después cambia la disponibilidad: el usuario debe generar otra reserva.
- Usar el mismo reservation_id con otro destino u operation_id devuelve 409. Un registro released no puede asignarse nuevamente y devuelve 409 `ASSIGNMENT_CLOSED`.
- Liberar solo elimina `assigned_reservation_id` si coincide con la reserva solicitada. No altera la ocupación ni el reporte del sensor.
- DELETE crea o actualiza un registro terminal released incluso si la asignación todavía no existe, para impedir que un PUT atrasado asigne después de una cancelación. Este registro de cierre se conserva todo el prototipo.
- PUT y DELETE para el mismo reservation_id se serializan con una garantía en PostgreSQL, por ejemplo un lock transaccional por clave y restricción única. PUT bloquea/actualiza la plaza en la misma transacción. DELETE no puede ignorar una creación simultánea todavía no visible. No se confía en el orden de llegada de las llamadas HTTP.
- La transición de asignación y la actualización del sensor sobre una plaza se serializan en PostgreSQL. Si el sensor reporta ocupación después de una asignación válida, se conserva la reserva y la plaza pasa a occupied.

### 4.2 Recuperación de Reservas

Transiciones permitidas:

| Desde | Hacia | Condición |
|---|---|---|
| pending | confirmed | Parkings confirma assigned y no hay cancelación aceptada |
| pending | rejected | Parkings devuelve rechazo definitivo |
| pending o confirmed | cancel_pending | Usuario solicita cancelar |
| cancel_pending | cancelled | Parkings confirma el registro released |

Pasos de creación: persistir pending y clave → llamar PUT con IDs estables → persistir confirmed o rejected y su outbox cuando corresponda. Para cancelación: persistir cancel_pending → llamar DELETE → persistir cancelled y su outbox.

Un trabajador revisa pendientes cada 5 s, con reintentos de 5, 15 y hasta 60 s de intervalo. Los fallos transitorios no convierten una reserva en rejected. Se registra alerta tras 60 s pendiente y se sigue intentando. Este plazo es operativo, no un vencimiento de la asignación.

La revisión usa reclamo de trabajo con lease expirable en PostgreSQL y actualizaciones condicionales por versión/estado. Si una instancia cae, otra retoma. Ninguna respuesta tardía puede cambiar cancel_pending/cancelled a confirmed. Una asignación sin confirmación se reconcilia repitiendo el mismo PUT o consultando el registro; una cancelación aceptada sigue el camino de DELETE. No se compensa un timeout suponiendo que no hubo asignación.

No hay transacción global entre servicios. La garantía propuesta es recuperación eventual bajo reanudación de los componentes y preservación de las bases. Un daño permanente de datos requiere intervención y queda fuera de esta recuperación automática.

### 4.3 Usuarios para Notificaciones

`GET /internal/v1/usuarios/{user_id}/destinatario` — solo Notificaciones. 200 `{user_id,email,name}`. 404 si no existe. Este endpoint es una propuesta de integración para evitar incluir emails en todos los eventos. Una indisponibilidad transitoria se reintenta; un destinatario inexistente es fallo permanente de notificación.

### 4.4 Salud

Cada API expone internamente `GET /health/live` (200 si el proceso responde) y `GET /health/ready` (200 si puede atender su función; 503 si falta una dependencia requerida). No requieren token y no incluyen secretos; NGINX no los publica. Los workers sin servidor HTTP usan un chequeo de salud del proceso y de su conexión en Compose.

Con outbox, Reservas puede aceptar operaciones si su DB funciona aunque RabbitMQ esté caído; la publicación queda pendiente. Parkings también puede operar con DB y reportes todavía vigentes. No se exige que RabbitMQ responda para marcar listas todas las APIs; la condición se define por función. Si Parkings no responde después de persistir una reserva, esta queda pending con respuesta 202.

## 5. Contrato de eventos

### 5.1 Sobre común

```json
{
  "event_id": "688ece42-351d-46ab-8a3c-a601a2f720bf",
  "event_type": "reservation.created.v1",
  "schema_version": 1,
  "occurred_at": "2026-10-21T14:00:00Z",
  "producer": "reservas",
  "correlation_id": "d2043f50-9d07-4ab2-869d-eec973844f75",
  "data": {}
}
```

Todos esos campos son obligatorios. `event_id` es globalmente único, se genera al registrar el evento y se conserva en cada reintento. La routing key coincide exactamente con `event_type`. Propiedades AMQP: `content_type=application/json`, `delivery_mode=2`, `message_id=event_id`, `correlation_id` igual al sobre y `type=event_type`.

Los sensores generan un correlation_id por reporte. Los eventos derivados de ese reporte conservan el mismo. La detección periódica de stale genera uno nuevo por transición. Las operaciones de recuperación conservan el correlation_id de la operación original y registran además el intento local.

### 5.2 Catálogo

| Tipo / routing key | Productor | Consumidores | Cuándo |
|---|---|---|---|
| `sensor.reported.v1` | sensores | Parkings | Cada intervalo, y ante cambio físico |
| `parking.spot_initialized.v1` | Parkings | Métricas | Alta inicial de una plaza en el seed |
| `parking.availability_changed.v1` | Parkings | Métricas | Cambia disponibilidad, asignación o estado físico aceptado |
| `parking.sensor_stale.v1` | Parkings | Métricas | Transición a datos desactualizados |
| `parking.sensor_recovered.v1` | Parkings | Métricas | Primer reporte vigente tras stale |
| `parking.sensor_refreshed.v1` | Parkings | Métricas | Reporte vigente que solo renueva vigencia |
| `reservation.created.v1` | Reservas | Métricas y Notificaciones | Reserva pasa a confirmed |
| `reservation.cancelled.v1` | Reservas | Métricas y Notificaciones | Reserva pasa a cancelled, incluso si nunca se confirmó |

No se publican eventos de reserva confirmada desde Parkings: solo Reservas determina su confirmación. Pending y rejected no cuentan como reservas creadas.

En v1, los avisos al usuario son confirmación/cancelación. Notificaciones no consume cada cambio físico porque no hay una regla definida de suscripción de usuarios. Alertas de vigencia y cambios de disponibilidad se muestran en el dashboard mediante Métricas. Esto concreta qué eventos son pertinentes para cada consumidor.

`sensor_refreshed` e `initialized` se proponen para que Métricas conozca todas las plazas y la última vigencia aunque no cambie su disponibilidad.

### 5.3 Reporte del sensor

`sensor.reported.v1`, `data`:

```json
{
  "sensor_id": "63d6ab4a-ecda-4353-a907-28a93ebf1d88",
  "spot_id": "1c51fda6-45da-4db4-9a5b-94b4ce7b796a",
  "sequence": 42,
  "observed_at": "2026-10-21T14:00:00Z",
  "physical_occupied": false
}
```

- `sequence` es un entero positivo, monotónico por sensor, persistido en un volumen del simulador. Un reinicio no lo vuelve a 1. Si se pierde su almacenamiento, se requiere un reinicio coordinado de los datos de prueba; no se inventa una nueva secuencia aceptable.
- Identidad sensor/plaza debe coincidir con el seed. El simulador solo publica para sus sensores; sus credenciales RabbitMQ permiten publicar en el exchange de sensores, sin consumir datos de otros servicios.
- Configuración propuesta: reporte cada 5 s; vigencia máxima 15 s desde observed_at; verificación de stale cada 2 s; tolerancia futura máxima de reloj 2 s. Observaciones futuras dentro de esa tolerancia se limitan a la hora de recepción para calcular vigencia; fechas mayores se rechazan.
- Se aceptan únicamente sequence mayor que la última aceptada, observed_at no anterior al último aceptado y datos aún vigentes según el reloj de Parkings.
- Los reportes duplicados, con secuencia antigua o ya vencidos se descartan con log y ACK, sin modificar ocupación, última observación aceptada ni vigencia. Un reporte retrasado no se rejuvenece por su hora de recepción.
- El simulador conserva secuencia antes de publicar y reintenta con el mismo evento hasta recibir publisher confirm; puede saltar números tras una caída, pero no reutilizarlos con otro reporte. No se exige conservar todos los cambios físicos producidos mientras está apagado; al volver informa el estado actual.

### 5.4 Eventos de Parkings

Todos los eventos de Parkings llevan `data.spot` con la instantánea completa de `Spot`, más `data.reason`:

- initialized: `initial_state`.
- availability_changed: `sensor_state_changed`, `assignment_created` o `assignment_released`.
- sensor_stale: `report_timeout`.
- sensor_recovered: `fresh_report_received`.
- sensor_refreshed: `heartbeat_received`.

Un cambio de reserva asignada a otra siempre pasa por liberación/asignación y emite la nueva instantánea, aunque la categoría visual no cambie. Cada transacción de cambio de plaza incrementa version y registra un único evento de snapshot. Si coinciden varias razones se prioriza recovered → availability_changed → refreshed; stale e initialized tienen su propia transición. La instantánea contiene todos los campos resultantes, así no se necesita otro evento de esa misma transición.

Un heartbeat vigente aumenta version y renueva el snapshot para Métricas, incluso si no cambia la categoría. La expiración puede hacerse efectiva al leer antes de ejecutarse el worker; la transición persistida a stale se realiza una sola vez, con outbox y nueva versión. Si justo llega un reporte, la transacción serializada resuelve el estado final.

### 5.5 Eventos de Reservas

Ambos tipos contienen `data.reservation` con la instantánea completa de Reservation. Para created: status=confirmed, ever_confirmed=true. Para cancelled: status=cancelled; ever_confirmed puede ser false si se canceló mientras estaba pending.

Métricas guarda la instantánea de mayor version por reserva. `ever_confirmed` y las fechas permiten calcular acumulados aunque cancelled llegue antes que created. Los duplicados o versiones anteriores no incrementan contadores. Preferentemente se calculan indicadores sobre la proyección persistida en lugar de sumar ciegamente +1 por mensaje.

Notificaciones usa las instantáneas para no enviar una confirmación antigua después de haber procesado la cancelación: si ya conoce una versión terminal posterior, registra el mensaje viejo como suprimido y hace ACK. Si la confirmación ya se entregó antes de conocer la cancelación, entrega luego la cancelación; no puede retirar un aviso entregado. La cancelación de una reserva nunca confirmada puede producir un aviso «Solicitud cancelada», sin afirmar que había una reserva confirmada.

## 6. Topología RabbitMQ y garantías

### 6.1 Exchanges y colas

Exchanges topic durables: `sensors.events`, `parking.events`, `reservations.events`. Exchange direct durable para fallos: `system.dlx`.

| Cola durable | Exchange y bindings |
|---|---|
| `parkings.sensor.q` | sensors.events: `sensor.reported.v1` |
| `metricas.parking.q` | parking.events: los cinco tipos de Parkings del catálogo, mediante bindings explícitos |
| `metricas.reservas.q` | reservations.events: `reservation.created.v1`, `reservation.cancelled.v1` |
| `notificaciones.reservas.q` | reservations.events: `reservation.created.v1`, `reservation.cancelled.v1` |

Cada cola principal tiene su propia cola final `<cola>.dlq`, enrutada desde `system.dlx` mediante una clave igual al nombre de la cola principal. No se usa TTL en la cola principal ni se borran sus mensajes al cerrar el consumidor. Las colas se declaran antes de aceptar operaciones y se conservan aunque el consumidor esté detenido.

Métricas y Notificaciones tienen colas distintas para recibir ambos los eventos de reserva. Réplicas del mismo consumidor comparten su cola, no crean una cola por instancia. `prefetch_count=1` como punto inicial para la demostración; no implica orden global ni elimina la necesidad de control de versiones.

### 6.2 Publicación y consumo

- Cambios de dominio, versión y outbox en una misma transacción PostgreSQL. El relay publica con publisher confirms y `mandatory=true`; trata una publicación sin ruta como fallo, no como éxito.
- Si un confirm se pierde se puede republicar; por eso event_id se conserva. El relay no garantiza orden global. Los snapshots/versiones resuelven desorden en las proyecciones.
- ACK manual después del commit local. Si hay caída antes del ACK, puede haber reentrega.
- Registro `processed_events` con clave única `(consumer_name,event_id)`, persistido en la misma transacción que el efecto local. Es compartido por todas las réplicas del mismo consumidor y se conserva todo el prototipo.
- Para una proyección, registro de deduplicación y aplicación por versión son atómicos. La deduplicación por event_id y el control de version resuelven problemas distintos.
- Garantía: entrega al menos una vez bajo persistencia y recuperación de componentes, no exactamente una vez. Un único broker no implica alta disponibilidad ni protección contra pérdida de su disco.

### 6.3 Reintentos y DLQ

Cada cola tiene tres colas auxiliares de reintento, con TTL fijo de 5 s, 15 s y 60 s. Cada una devuelve los mensajes mediante un exchange direct de retorno a su cola principal. El destino original se fija en la topología, no se acepta de datos arbitrarios del mensaje.

Ante fallo transitorio se republica en la siguiente cola de reintento, se espera confirmación y solo después se confirma el mensaje original. Se conserva el sobre y event_id; se aumenta la cabecera `x-retry-count` (0 por defecto). Si la republicación falla, no se hace ACK y se restablece la conexión o se reintenta con pausa; no se crea un bucle inmediato ilimitado de requeue.

Tras tres reintentos fallidos, o ante JSON/esquema inválido, UUID de sensor desconocido o error permanente, se envía a la DLQ mediante rechazo sin requeue/configuración de dead-letter. Los duplicados y reportes viejos válidos se descartan con ACK; no van a DLQ. La DLQ conserva sobre original y metadatos técnicos de fallo, sin secretos. Su reproducción es manual, después de corregir la causa; mantiene event_id y restablece el contador de reintento.

No se ofrece recuperación automática ante toda pérdida ocurrida durante el traslado interno de dead-letter de un broker único. Para la demostración, el objetivo es recuperación de consumidores temporariamente detenidos con RabbitMQ y su volumen disponibles.

### 6.4 Bootstrap

El seed crea plazas y eventos initialized en outbox con version=1; las plazas comienzan stale, sin asignación y con physical_occupied=null. Luego los reportes del simulador producen snapshots nuevos. Métricas recibe inicializaciones y actualizaciones aunque se encuentre detenida durante el seed porque sus colas ya existen.

No se elimina la base de Métricas conservando el resto y esperando que RabbitMQ reproduzca eventos ya confirmados: RabbitMQ no es un historial reproducible completo. Para reiniciar la demo se recrea el conjunto de datos de forma coordinada, o se incorpora una herramienta explícita de reconstrucción desde las APIs y snapshots. Esta segunda herramienta queda fuera de v1.

## 7. Notificaciones: contrato de entrega simulada

Canal v1: `simulated_email`. Plantillas: `reservation_confirmed`, `reservation_cancelled`, `request_cancelled`.

Registro persistido: `{delivery_id,event_id,reservation_id,reservation_version,user_id,template,channel,status,created_at,delivered_at}`. Estados: delivered o suppressed. Clave única `(event_id,channel)`; delivery_id UUID. Email de destino se resuelve en Usuarios y no se incluye en logs.

La entrega simulada consiste en guardar el registro delivered y el processed_events en una transacción, y luego emitir un log con delivery_id. El registro persistente es la evidencia; el log puede repetirse tras una caída. Las réplicas usan una restricción única y serialización por reservation_id para evitar efectos locales repetidos y comparar versiones.

No se envían emails reales en v1. Si se incorpora un proveedor externo, necesitará idempotencia propia o se aceptará el riesgo de duplicados: un registro local no convierte el envío externo en parte de una transacción PostgreSQL.

## 8. Logs y observabilidad

Cada proceso emite JSON por stdout/stderr. Campos obligatorios: `timestamp`, `level`, `service`, `instance_id`, `action`, `result`, `correlation_id` (null solo en tareas técnicas sin operación asociada). Campos según contexto: `http_method`, `path`, `status_code`, `duration_ms`, `reservation_id`, `spot_id`, `sensor_id`, `operation_id`, `event_id`, `entity_version`, `attempt`, `error_code`.

Acciones mínimas: `http_received`, `http_completed`, `assignment_created`, `assignment_rejected`, `assignment_released`, `reservation_pending`, `reservation_confirmed`, `reservation_cancelled`, `recovery_attempted`, `event_published`, `event_processed`, `event_duplicate`, `event_discarded`, `event_failed`, `sensor_stale`, `sensor_recovered`, `notification_delivered`.

INFO para procesamiento normal; WARNING para conflicto, descarte por antigüedad, datos stale y reintentos; ERROR para fallos no resueltos y DLQ. Los conflictos de negocio no generan trazas de excepción como si fueran fallos de programación. NGINX registra correlación y resultado. Los errores HTTP mantienen el mismo correlation_id de la operación.

Para servicios internos se propaga X-Correlation-ID; para AMQP se copia al sobre y a la propiedad. La correlación no constituye trazas distribuidas. Docker configura rotación y retención; los logs no sustituyen datos de negocio ni registros de entrega.

## 9. Compatibilidad y responsabilidades de implementación

- Prefijo REST v1 y tipos de evento terminados en .v1. Cambios incompatibles crean v2; añadir un campo opcional puede mantener v1.
- Los consumidores aceptan schema_version=1 e ignoran campos desconocidos. Un tipo sin soporte no se enlaza; si llega de todos modos a una cola por error de topología se registra y deriva a DLQ.
- Los contratos HTTP deberán plasmarse en OpenAPI de cada FastAPI. Los eventos se validarán con esquemas JSON/Pydantic compartidos como artefactos de contrato, sin compartir modelos de persistencia entre servicios.
- Este documento fija semántica, rutas, campos y garantías; no afirma que existan todavía los archivos OpenAPI/JSON Schema ni pruebas ejecutadas.
- Valores configurables iniciales: SENSOR_REPORT_INTERVAL_SECONDS=5; SENSOR_MAX_AGE_SECONDS=15; SENSOR_CHECK_INTERVAL_SECONDS=2; SENSOR_CLOCK_SKEW_SECONDS=2; RECOVERY_POLL_SECONDS=5; DASHBOARD_POLL_SECONDS=5. Cambiar estos valores exige mantener la misma semántica de vigencia y ajustar las pruebas.

## 10. Criterios de aceptación de los contratos

| Caso | Verificación |
|---|---|
| Registro repetido | Email único; 409 y sin segundo usuario |
| Credenciales/rol | Token inválido: 401; usuario común en Métricas: 403 |
| Reserva ajena | No se puede leer ni cancelar; 404 |
| Concurrencia | Dos IDs de reserva distintos sobre una plaza: solo una asignación |
| Reintento de creación | Misma clave y cuerpo: mismo ID de reserva |
| Uso incorrecto de clave | Misma clave y otro destino: 409 |
| Timeout tras asignar | Se recupera la misma operación, sin asignación extra |
| Cancelación simultánea | Un PUT atrasado no revive una asignación released |
| Liberación atrasada | No borra la asignación de otra reserva |
| Sensor informa libre | No elimina una asignación existente |
| Cancelar plaza ocupada | Queda sin asignación, pero no disponible |
| Sensor sin reportes | No acepta asignación al expirar, aunque el checker aún no haya corrido |
| Reporte viejo | No cambia ocupación ni renueva vigencia |
| Reinicio del simulador | La secuencia no retrocede |
| Reentrega AMQP | No duplica proyección ni registro de entrega simulada |
| Eventos desordenados | Se conserva la mayor versión y los acumulados correctos |
| Consumidor detenido | Los eventos pendientes se procesan al volver; el broker sigue disponible |
| Broker temporalmente caído | Los cambios persistidos con outbox se publican al recuperarse |
| Réplicas de Notificaciones | Comparten cola y deduplicación; se identifica la instancia en logs |
| Correlación | Se relacionan HTTP, operación interna y evento por correlation_id |
| Dashboard | Distingue unknown, no suma categorías superpuestas y muestra consistencia eventual |

Estas son pruebas por implementar y ejecutar, no resultados ya obtenidos.

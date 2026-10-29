from fastapi import APIRouter, Depends

from app.errors import ApiError
from app.fleet import sensor_definitions, sensor_states
from app.schemas import FailureUpdate, OccupancyUpdate, SimulatedSensor
from app.security import require_sensor
from app.state import SensorState


public_router = APIRouter(
    prefix="/api/v1/simulacion/sensores",
    tags=["simulacion"],
    dependencies=[Depends(require_sensor)],
)
health_router = APIRouter(tags=["health"])


def find(label: str) -> tuple[dict[str, str], SensorState]:
    normalized = label.upper()
    value = next(((definition, state) for definition, state in zip(sensor_definitions(), sensor_states())
                  if definition["label"] == normalized), None)
    if value is None:
        raise ApiError(404, "RESOURCE_NOT_FOUND", "El sensor solicitado no existe.")
    return value


def read_sensor(definition: dict[str, str], state: SensorState) -> SimulatedSensor:
    value = state.inspect()
    return SimulatedSensor(
        label=definition["label"], sensor_id=value["sensor_id"], spot_id=value["spot_id"],
        status="stopped" if value["failed"] else "active", sequence=value["sequence"],
        physical_occupied=value["physical_occupied"], updated_at=value["updated_at"],
    )


@public_router.get("", response_model=list[SimulatedSensor])
def list_sensors() -> list[SimulatedSensor]:
    return [read_sensor(definition, state)
            for definition, state in zip(sensor_definitions(), sensor_states())]


@public_router.put("/{label}", response_model=SimulatedSensor)
def update_sensor(label: str, payload: FailureUpdate) -> SimulatedSensor:
    definition, state = find(label)
    state.set_failed(payload.failed)
    return read_sensor(definition, state)


@public_router.put("/{label}/occupancy", response_model=SimulatedSensor)
def update_sensor_occupancy(label: str, payload: OccupancyUpdate) -> SimulatedSensor:
    definition, state = find(label)
    state.set_occupied(payload.occupied)
    return read_sensor(definition, state)


@health_router.get("/health/live")
def live() -> dict[str, str]:
    return {"status": "live"}


@health_router.get("/health/ready")
def ready() -> dict[str, str]:
    sensor_states()[0].inspect()
    return {"status": "ready"}

from functools import lru_cache

from app.catalog import configured_sensors
from app.config import get_settings
from app.state import SensorState


def sensor_definitions() -> list[dict[str, str]]:
    settings = get_settings()
    if settings.simulate_full_parking:
        return configured_sensors()
    return [{"sensor_id": settings.sensor_id, "spot_id": settings.spot_id, "label": "A-01"}]


@lru_cache
def sensor_states() -> tuple[SensorState, ...]:
    settings = get_settings()
    return tuple(SensorState(settings.state_db_path, item["sensor_id"], item["spot_id"])
                 for item in sensor_definitions())

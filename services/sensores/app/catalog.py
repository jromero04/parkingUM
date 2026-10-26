import uuid


LEGACY_SPOT_ID = "22222222-2222-4222-8222-222222222222"
LEGACY_SENSOR_ID = "33333333-3333-4333-8333-333333333333"
SPOT_NAMESPACE = uuid.UUID("7f5d47ca-c97a-46ca-ae0a-b617111c353e")
SENSOR_NAMESPACE = uuid.UUID("58ec9e88-bde6-4f5c-8219-e95395dd7dcc")
ZONE_CAPACITIES = {"A": 72, "B": 18, "C": 78}


def spot_id_for(label: str) -> str:
    if label == "A-01":
        return LEGACY_SPOT_ID
    return str(uuid.uuid5(SPOT_NAMESPACE, label))


def sensor_id_for(label: str) -> str:
    if label == "A-01":
        return LEGACY_SENSOR_ID
    return str(uuid.uuid5(SENSOR_NAMESPACE, label))


def configured_sensors() -> list[dict[str, str]]:
    return [
        {"sensor_id": sensor_id_for(label), "spot_id": spot_id_for(label), "label": label}
        for zone, capacity in ZONE_CAPACITIES.items()
        for number in range(1, capacity + 1)
        for label in [f"{zone}-{number:02d}"]
    ]

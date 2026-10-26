from app.catalog import configured_sensors


def test_full_parking_has_one_sensor_per_spot():
    sensors = configured_sensors()
    assert len(sensors) == 168
    assert len({item["sensor_id"] for item in sensors}) == 168
    assert len({item["spot_id"] for item in sensors}) == 168
    assert sensors[0]["label"] == "A-01"
    assert sensors[-1]["label"] == "C-78"

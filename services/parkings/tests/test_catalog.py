from app.catalog import LEGACY_SENSOR_ID, LEGACY_SPOT_ID, configured_spots


def test_catalog_contains_every_mapped_spot_and_unique_sensor():
    spots = configured_spots()
    assert len(spots) == 168
    assert len({spot["id"] for spot in spots}) == 168
    assert len({spot["sensor_id"] for spot in spots}) == 168
    assert [spot["label"] for spot in spots[:2]] == ["A-01", "A-02"]
    assert spots[-1]["label"] == "C-78"
    assert spots[0]["id"] == LEGACY_SPOT_ID
    assert spots[0]["sensor_id"] == LEGACY_SENSOR_ID

import json
import logging

from app.logging_config import JsonFormatter


def test_json_formatter_emits_required_observability_fields():
    record = logging.LogRecord("test", logging.INFO, __file__, 1, "", (), None)
    record.service = "parkings"
    record.instance_id = "test-instance"
    record.action = "assignment_created"
    record.result = "success"
    record.correlation_id = "d2043f50-9d07-4ab2-869d-eec973844f75"
    record.reservation_id = "688ece42-351d-46ab-8a3c-a601a2f720bf"

    payload = json.loads(JsonFormatter().format(record))

    assert payload["timestamp"].endswith("Z")
    assert payload["level"] == "INFO"
    assert payload["service"] == "parkings"
    assert payload["instance_id"] == "test-instance"
    assert payload["action"] == "assignment_created"
    assert payload["result"] == "success"
    assert payload["correlation_id"] == "d2043f50-9d07-4ab2-869d-eec973844f75"
    assert payload["reservation_id"] == "688ece42-351d-46ab-8a3c-a601a2f720bf"

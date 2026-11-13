from prometheus_client import Counter


SENSOR_EVENTS_PROCESSED = Counter(
    "sensor_events_processed_total",
    "Total de eventos de sensores procesados.",
    ("result",),
)
for result in ("accepted", "duplicate", "discarded", "invalid", "retry", "dlq"):
    SENSOR_EVENTS_PROCESSED.labels(result=result)

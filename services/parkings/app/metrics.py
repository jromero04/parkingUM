from fastapi import Request, Response
from prometheus_client import Counter


HTTP_REQUESTS = Counter(
    "http_requests_total",
    "Total de solicitudes HTTP procesadas.",
    ("service", "route", "method", "status"),
)
PARKING_ASSIGNMENTS = Counter(
    "parking_assignments_total",
    "Total de intentos de asignacion de plazas.",
    ("result",),
)
for result in ("assigned", "duplicate", "rejected", "other"):
    PARKING_ASSIGNMENTS.labels(result=result)


def record_http_request(request: Request, response: Response) -> None:
    route = getattr(request.scope.get("route"), "path", "unmatched")
    if route.startswith(("/health/", "/metrics")):
        return
    HTTP_REQUESTS.labels(
        service="parkings",
        route=route,
        method=request.method,
        status=str(response.status_code),
    ).inc()
    if route == "/internal/v1/asignaciones/{reservation_id}" and request.method == "PUT":
        result = {
            200: "duplicate",
            201: "assigned",
        }.get(response.status_code, "rejected" if response.status_code >= 400 else "other")
        PARKING_ASSIGNMENTS.labels(result=result).inc()

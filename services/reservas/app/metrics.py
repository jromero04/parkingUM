from fastapi import Request, Response
from prometheus_client import Counter


HTTP_REQUESTS = Counter(
    "http_requests_total",
    "Total de solicitudes HTTP procesadas.",
    ("service", "route", "method", "status"),
)
RESERVATIONS_CREATED = Counter(
    "reservations_created_total",
    "Total de solicitudes de creacion de reservas.",
    ("result",),
)
for result in ("confirmed", "pending", "rejected", "other"):
    RESERVATIONS_CREATED.labels(result=result)


def record_http_request(request: Request, response: Response) -> None:
    route = getattr(request.scope.get("route"), "path", "unmatched")
    if route.startswith(("/health/", "/metrics")):
        return
    HTTP_REQUESTS.labels(
        service="reservas",
        route=route,
        method=request.method,
        status=str(response.status_code),
    ).inc()
    if route == "/api/v1/reservas" and request.method == "POST":
        result = {
            201: "confirmed",
            202: "pending",
        }.get(response.status_code, "rejected" if response.status_code >= 400 else "other")
        RESERVATIONS_CREATED.labels(result=result).inc()

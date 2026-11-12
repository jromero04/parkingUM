from fastapi import Request, Response
from prometheus_client import Counter


HTTP_REQUESTS = Counter(
    "http_requests_total",
    "Total de solicitudes HTTP procesadas.",
    ("service", "route", "method", "status"),
)


def record_http_request(request: Request, response: Response) -> None:
    route = getattr(request.scope.get("route"), "path", "unmatched")
    if route.startswith(("/health/", "/metrics")):
        return
    HTTP_REQUESTS.labels(
        service="metricas",
        route=route,
        method=request.method,
        status=str(response.status_code),
    ).inc()

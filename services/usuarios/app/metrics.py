from fastapi import Request, Response
from prometheus_client import Counter


HTTP_REQUESTS = Counter(
    "http_requests_total",
    "Total de solicitudes HTTP procesadas.",
    ("service", "route", "method", "status"),
)
LOGIN_ATTEMPTS = Counter(
    "login_attempts_total",
    "Total de intentos de inicio de sesion.",
    ("result",),
)
for result in ("success", "invalid_credentials", "rejected"):
    LOGIN_ATTEMPTS.labels(result=result)


def record_http_request(request: Request, response: Response) -> None:
    route = getattr(request.scope.get("route"), "path", "unmatched")
    if route.startswith(("/health/", "/metrics")):
        return
    HTTP_REQUESTS.labels(
        service="usuarios",
        route=route,
        method=request.method,
        status=str(response.status_code),
    ).inc()
    if route == "/api/v1/usuarios/login" and request.method == "POST":
        result = "success" if response.status_code == 200 else "invalid_credentials" if response.status_code == 401 else "rejected"
        LOGIN_ATTEMPTS.labels(result=result).inc()

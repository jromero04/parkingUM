import logging
import time
import uuid

from fastapi import Request, Response

from app.config import get_settings
from app.logging_config import log_event


logger = logging.getLogger("parkings.http")


def valid_correlation_id(value: str | None) -> str:
    try:
        return str(uuid.UUID(value)) if value else str(uuid.uuid4())
    except ValueError:
        return str(uuid.uuid4())


async def correlation_and_logging_middleware(request: Request, call_next) -> Response:
    correlation_id = valid_correlation_id(request.headers.get("X-Correlation-ID"))
    request.state.correlation_id = correlation_id
    started = time.perf_counter()
    log_event(
        logger,
        "http_received",
        "received",
        correlation_id=correlation_id,
        http_method=request.method,
        path=request.url.path,
        service=get_settings().service_name,
    )
    response = await call_next(request)
    response.headers["X-Correlation-ID"] = correlation_id
    log_event(
        logger,
        "http_completed",
        "success" if response.status_code < 400 else "error",
        correlation_id=correlation_id,
        http_method=request.method,
        path=request.url.path,
        status_code=response.status_code,
        duration_ms=round((time.perf_counter() - started) * 1000, 2),
        service=get_settings().service_name,
    )
    return response

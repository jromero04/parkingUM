import json
import logging
import os
import time
from datetime import datetime, timezone
from uuid import UUID, uuid4

from fastapi import Request

logger = logging.getLogger("usuarios.http")


def valid_correlation_id(value: str | None) -> str:
    if value:
        try:
            return str(UUID(value))
        except ValueError:
            pass
    return str(uuid4())


async def correlation_and_logging_middleware(request: Request, call_next):
    correlation_id = valid_correlation_id(request.headers.get("X-Correlation-ID"))
    request.state.correlation_id = correlation_id
    started = time.perf_counter()
    response = await call_next(request)
    duration_ms = round((time.perf_counter() - started) * 1000, 2)
    response.headers["X-Correlation-ID"] = correlation_id
    logger.info(
        json.dumps(
            {
                "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                "level": "INFO",
                "service": "usuarios",
                "instance_id": os.getenv("HOSTNAME", "local"),
                "action": "http_completed",
                "result": "success" if response.status_code < 400 else "error",
                "correlation_id": correlation_id,
                "http_method": request.method,
                "path": request.url.path,
                "status_code": response.status_code,
                "duration_ms": duration_ms,
            },
            separators=(",", ":"),
        )
    )
    return response


from typing import Any
import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.logging_config import log_event


logger = logging.getLogger("parkings.errors")


class ApiError(Exception):
    def __init__(self, status_code: int, code: str, message: str, details: dict[str, Any] | None = None) -> None:
        self.status_code = status_code
        self.code = code
        self.message = message
        self.details = details or {}


def error_response(request: Request, status: int, code: str, message: str, details: dict[str, Any]) -> JSONResponse:
    return JSONResponse(
        status_code=status,
        content={
            "error": {"code": code, "message": message, "details": details},
            "correlation_id": request.state.correlation_id,
        },
        headers={"X-Correlation-ID": request.state.correlation_id},
    )


def install_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(ApiError)
    async def handle_api_error(request: Request, exc: ApiError) -> JSONResponse:
        return error_response(request, exc.status_code, exc.code, exc.message, exc.details)

    @app.exception_handler(RequestValidationError)
    async def handle_validation(request: Request, exc: RequestValidationError) -> JSONResponse:
        fields = [
            {"field": ".".join(str(part) for part in error["loc"] if part != "body"), "reason": error["msg"]}
            for error in exc.errors()
        ]
        return error_response(request, 422, "VALIDATION_ERROR", "La solicitud contiene datos invalidos.", {"fields": fields})

    @app.exception_handler(Exception)
    async def handle_unexpected(request: Request, exc: Exception) -> JSONResponse:
        logger.exception(
            "Error inesperado",
            exc_info=(type(exc), exc, exc.__traceback__),
            extra={
                "action": "event_failed",
                "result": "error",
                "correlation_id": request.state.correlation_id,
                "error_code": "INTERNAL_ERROR",
            },
        )
        return error_response(request, 500, "INTERNAL_ERROR", "Ocurrio un error interno.", {})

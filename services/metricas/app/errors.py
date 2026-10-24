import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


logger = logging.getLogger("metricas.errors")


class ApiError(Exception):
    def __init__(self, status_code: int, code: str, message: str, details: dict[str, Any] | None = None) -> None:
        self.status_code, self.code, self.message = status_code, code, message
        self.details = details or {}


def error_response(request: Request, status: int, code: str, message: str, details: dict) -> JSONResponse:
    return JSONResponse(status_code=status,
                        content={"error": {"code": code, "message": message, "details": details},
                                 "correlation_id": request.state.correlation_id},
                        headers={"X-Correlation-ID": request.state.correlation_id})


def install_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(ApiError)
    async def api_error(request: Request, exc: ApiError) -> JSONResponse:
        return error_response(request, exc.status_code, exc.code, exc.message, exc.details)

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        fields = [{"field": ".".join(str(item) for item in error["loc"] if item != "body"),
                   "reason": error["msg"]} for error in exc.errors()]
        return error_response(request, 422, "VALIDATION_ERROR", "La solicitud contiene datos invalidos.",
                              {"fields": fields})

    @app.exception_handler(Exception)
    async def unexpected(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("Error inesperado", extra={"action": "event_failed", "result": "error",
                                                     "correlation_id": request.state.correlation_id})
        return error_response(request, 500, "INTERNAL_ERROR", "Ocurrio un error interno.", {})

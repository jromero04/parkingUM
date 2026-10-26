from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


class ApiError(Exception):
    def __init__(self, status_code: int, code: str, message: str, details: dict[str, Any] | None = None) -> None:
        self.status_code = status_code
        self.code = code
        self.message = message
        self.details = details or {}


def response(request: Request, status: int, code: str, message: str, details: dict[str, Any]) -> JSONResponse:
    correlation_id = getattr(request.state, "correlation_id", None)
    return JSONResponse(
        status_code=status,
        content={"error": {"code": code, "message": message, "details": details},
                 "correlation_id": correlation_id},
        headers={"X-Correlation-ID": correlation_id} if correlation_id else None,
    )


def install_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(ApiError)
    async def api_error(request: Request, exc: ApiError) -> JSONResponse:
        return response(request, exc.status_code, exc.code, exc.message, exc.details)

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        fields = [{"field": ".".join(str(item) for item in error["loc"] if item != "body"),
                   "reason": error["msg"]} for error in exc.errors()]
        return response(request, 422, "VALIDATION_ERROR", "La solicitud contiene datos invalidos.",
                        {"fields": fields})

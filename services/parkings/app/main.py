import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.errors import install_exception_handlers
from app.middleware import correlation_and_logging_middleware
from app.routes import health_router, internal_router, public_router


logging.basicConfig(level=logging.INFO, format="%(message)s")
settings = get_settings()

app = FastAPI(title="Servicio de Parkings", version="1.0.0", docs_url="/docs", openapi_url="/openapi.json")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.cors_origin],
    allow_credentials=False,
    allow_methods=["GET"],
    allow_headers=["Authorization", "Content-Type", "X-Correlation-ID"],
)
app.middleware("http")(correlation_and_logging_middleware)
install_exception_handlers(app)
app.include_router(public_router)
app.include_router(internal_router)
app.include_router(health_router)

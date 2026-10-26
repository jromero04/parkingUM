import asyncio
import threading
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.errors import install_exception_handlers
from app.fleet import sensor_states
from app.logging_config import configure_logging
from app.publisher import run as run_publisher
from app.routes import health_router, public_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    sensor_states()
    if get_settings().start_publisher:
        threading.Thread(target=run_publisher, daemon=True, name="sensor-publisher").start()
    yield
    await asyncio.sleep(0)


configure_logging()
settings = get_settings()
app = FastAPI(title="Control del simulador de sensores", version="1.0.0", lifespan=lifespan,
              docs_url=None, openapi_url=None)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.cors_origin], allow_credentials=False,
    allow_methods=["GET", "PUT"], allow_headers=["Authorization", "Content-Type", "X-Correlation-ID"],
)


@app.middleware("http")
async def correlation_id(request: Request, call_next):
    supplied = request.headers.get("X-Correlation-ID")
    try:
        request.state.correlation_id = str(uuid.UUID(supplied)) if supplied else str(uuid.uuid4())
    except ValueError:
        request.state.correlation_id = str(uuid.uuid4())
    response = await call_next(request)
    response.headers["X-Correlation-ID"] = request.state.correlation_id
    return response


install_exception_handlers(app)
app.include_router(public_router)
app.include_router(health_router)

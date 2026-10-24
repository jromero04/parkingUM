from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    service_name: str = "reservas"
    database_url: str = "postgresql+psycopg://reservas_app:dev-only-password@reservas-db:5432/reservas_db"
    parkings_url: str = "http://parkings:8000"
    parkings_connect_timeout_seconds: float = Field(default=2.0, gt=0, le=10)
    parkings_read_timeout_seconds: float = Field(default=5.0, gt=0, le=30)
    reservations_service_token: str = "dev-only-reservations-token"
    jwt_issuer: str = "parking-users"
    jwt_audience: str = "parking-api"
    jwt_public_key_path: str = "/run/parking-keys/public.pem"
    rabbitmq_url: str = "amqp://parking_app:dev-only-rabbit-password@rabbitmq:5672/%2F"
    recovery_poll_seconds: float = Field(default=5.0, ge=0.1, le=60)
    recovery_lease_seconds: int = Field(default=30, ge=5, le=300)
    cors_origin: str = "http://localhost:3000"


@lru_cache
def get_settings() -> Settings:
    return Settings()

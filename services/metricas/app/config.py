from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    service_name: str = "metricas"
    database_url: str = "postgresql+psycopg://metricas_app:dev-only-password@metricas-db:5432/metricas_db"
    rabbitmq_url: str = "amqp://parking_app:dev-only-rabbit-password@rabbitmq:5672/%2F"
    jwt_issuer: str = "parking-users"
    jwt_audience: str = "parking-api"
    jwt_public_key_path: str = "/run/parking-keys/public.pem"
    cors_origin: str = "http://localhost:3000"


@lru_cache
def get_settings() -> Settings:
    return Settings()

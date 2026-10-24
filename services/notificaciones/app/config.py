from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    service_name: str = "notificaciones"
    database_url: str = "postgresql+psycopg://notificaciones_app:dev-only-password@notificaciones-db:5432/notificaciones_db"
    rabbitmq_url: str = "amqp://parking_app:dev-only-rabbit-password@rabbitmq:5672/%2F"
    usuarios_url: str = "http://usuarios:8000"
    notifications_service_token: str = "dev-only-notifications-token"
    usuarios_connect_timeout_seconds: float = 2.0
    usuarios_read_timeout_seconds: float = 5.0


@lru_cache
def get_settings() -> Settings:
    return Settings()

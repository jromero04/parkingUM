from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    service_name: str = "usuarios"
    database_url: str = "postgresql+psycopg://usuarios_app:dev-only-password@postgres:5432/usuarios_db"
    jwt_issuer: str = "parking-users"
    jwt_audience: str = "parking-api"
    jwt_expires_seconds: int = Field(default=3600, ge=60, le=86400)
    jwt_private_key_path: str = "/run/parking-keys/private.pem"
    jwt_public_key_path: str = "/run/parking-keys/public.pem"
    notifications_service_token: str = "dev-only-notifications-token"
    cors_origin: str = "http://localhost:3000"
    admin_name: str = ""
    admin_email: str = ""
    admin_password: str = ""


@lru_cache
def get_settings() -> Settings:
    return Settings()


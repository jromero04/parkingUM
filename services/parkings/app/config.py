from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    service_name: str = "parkings"
    database_url: str = "postgresql+psycopg://parkings_app:dev-only-password@parkings-db:5432/parkings_db"
    jwt_issuer: str = "parking-users"
    jwt_audience: str = "parking-api"
    jwt_public_key_path: str = "/run/parking-keys/public.pem"
    reservations_service_token: str = "dev-only-reservations-token"
    sensor_fresh_seconds: int = Field(default=15, ge=5, le=300)
    cors_origin: str = "http://localhost:3000"


@lru_cache
def get_settings() -> Settings:
    return Settings()

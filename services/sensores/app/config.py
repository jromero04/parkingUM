from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    service_name: str = "sensores"
    rabbitmq_url: str = "amqp://parking_app:dev-only-rabbit-password@rabbitmq:5672/%2F"
    state_db_path: str = "/data/sensors.db"
    sensor_id: str = "33333333-3333-4333-8333-333333333333"
    spot_id: str = "22222222-2222-4222-8222-222222222222"
    report_interval_seconds: float = Field(default=5, ge=0.2, le=300)
    simulator_enabled: bool = True
    simulate_full_parking: bool = True
    start_publisher: bool = True
    jwt_issuer: str = "parking-users"
    jwt_audience: str = "parking-api"
    jwt_public_key_path: str = "/run/parking-keys/public.pem"
    cors_origin: str = "http://localhost:3000"


@lru_cache
def get_settings() -> Settings:
    return Settings()

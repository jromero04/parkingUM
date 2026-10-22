from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ParkingRead(BaseModel):
    id: UUID
    name: str
    address: str
    created_at: datetime


class SpotRead(BaseModel):
    id: UUID
    parking_id: UUID
    sensor_id: UUID
    label: str
    physical_occupied: bool | None
    assigned_reservation_id: UUID | None
    sensor_status: Literal["fresh", "stale"]
    last_report_at: datetime | None
    sensor_expires_at: datetime | None
    availability: Literal["available", "reserved", "occupied", "unknown"]
    version: int
    updated_at: datetime


class AssignmentCreate(StrictModel):
    parking_id: UUID
    spot_id: UUID
    operation_id: UUID


class AssignmentRead(BaseModel):
    reservation_id: UUID
    parking_id: UUID | None
    spot_id: UUID | None
    operation_id: UUID | None
    status: Literal["assigned", "rejected", "released"]
    reason: str | None
    version: int
    updated_at: datetime


class SensorData(StrictModel):
    sensor_id: UUID
    spot_id: UUID
    sequence: int = Field(gt=0)
    observed_at: datetime
    physical_occupied: bool

    @field_validator("observed_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("observed_at debe incluir zona horaria")
        return value


class EventEnvelope(StrictModel):
    event_id: UUID
    event_type: Literal["sensor.reported.v1"]
    schema_version: Literal[1]
    occurred_at: datetime
    producer: str
    correlation_id: UUID
    data: SensorData

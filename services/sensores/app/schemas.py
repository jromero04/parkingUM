from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class FailureUpdate(StrictModel):
    failed: bool


class OccupancyUpdate(StrictModel):
    occupied: bool


class SimulatedSensor(BaseModel):
    label: str
    sensor_id: UUID
    spot_id: UUID
    status: Literal["active", "stopped"]
    sequence: int
    physical_occupied: bool
    updated_at: datetime

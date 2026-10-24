from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class CompatibleModel(BaseModel):
    model_config = ConfigDict(extra="ignore")


class ReservationSnapshot(CompatibleModel):
    id: UUID
    user_id: UUID
    parking_id: UUID
    spot_id: UUID
    status: Literal["confirmed", "cancelled"]
    ever_confirmed: bool
    created_at: datetime
    updated_at: datetime
    confirmed_at: datetime | None
    cancelled_at: datetime | None
    failure_code: str | None
    version: int = Field(ge=1)


class ReservationData(CompatibleModel):
    reservation: ReservationSnapshot


class EventEnvelope(CompatibleModel):
    event_id: UUID
    event_type: Literal["reservation.created.v1", "reservation.cancelled.v1"]
    schema_version: Literal[1]
    occurred_at: datetime
    producer: str
    correlation_id: UUID
    data: ReservationData


class Recipient(BaseModel):
    user_id: UUID
    email: EmailStr
    name: str

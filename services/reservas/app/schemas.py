from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


ReservationStatus = Literal["pending", "confirmed", "cancel_pending", "cancelled", "rejected"]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ReservationCreate(StrictModel):
    parking_id: UUID
    spot_id: UUID


class ReservationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    parking_id: UUID
    spot_id: UUID
    status: ReservationStatus
    ever_confirmed: bool
    created_at: datetime
    updated_at: datetime
    confirmed_at: datetime | None
    cancelled_at: datetime | None
    failure_code: str | None
    version: int


class ReservationResponse(BaseModel):
    reservation: ReservationRead


class ReservationCollection(BaseModel):
    items: list[ReservationRead]
    next_cursor: str | None

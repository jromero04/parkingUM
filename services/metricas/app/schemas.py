from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class CompatibleModel(BaseModel):
    model_config = ConfigDict(extra="ignore")


class SpotSnapshot(CompatibleModel):
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


class ReservationSnapshot(CompatibleModel):
    id: UUID
    user_id: UUID
    parking_id: UUID
    spot_id: UUID
    status: Literal["pending", "confirmed", "occupied", "used", "cancel_pending", "cancelled", "rejected"]
    ever_confirmed: bool
    created_at: datetime
    updated_at: datetime
    confirmed_at: datetime | None
    occupied_at: datetime | None = None
    used_at: datetime | None = None
    cancelled_at: datetime | None
    failure_code: str | None
    version: int


class ParkingData(CompatibleModel):
    spot: SpotSnapshot
    reason: str


class ReservationData(CompatibleModel):
    reservation: ReservationSnapshot


class EventEnvelope(CompatibleModel):
    event_id: UUID
    event_type: str
    schema_version: Literal[1]
    occurred_at: datetime
    producer: str
    correlation_id: UUID
    data: dict


class SpotCounts(BaseModel):
    total: int
    available: int
    reserved: int
    occupied: int
    unknown: int
    assigned_total: int
    physically_occupied_fresh: int


class ReservationCounts(BaseModel):
    confirmed_current: int
    created_total: int
    cancelled_total: int


class Occupancy(BaseModel):
    occupied_fresh: int
    fresh_total: int
    percentage: float | None


class MetricsSummary(BaseModel):
    parking_id: UUID | None
    spots: SpotCounts
    reservations: ReservationCounts
    occupancy: Occupancy
    last_projected_at: datetime | None
    computed_at: datetime
    consistency: Literal["eventual"] = "eventual"


class SensorAlert(BaseModel):
    spot_id: UUID
    parking_id: UUID
    sensor_id: UUID
    label: str
    code: Literal["SENSOR_DATA_STALE"] = "SENSOR_DATA_STALE"
    since: datetime
    last_report_at: datetime | None
    message: str = "No hay reportes vigentes del sensor."


class AlertsCollection(BaseModel):
    items: list[SensorAlert]
    next_cursor: str | None
    computed_at: datetime

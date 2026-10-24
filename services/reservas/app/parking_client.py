from dataclasses import dataclass
from typing import Literal

import httpx

from app.config import get_settings


@dataclass(frozen=True)
class ParkingResult:
    outcome: Literal["assigned", "released", "rejected", "transient"]
    http_status: int | None = None
    error_code: str | None = None
    reason: str | None = None


class ParkingClient:
    def __init__(self) -> None:
        settings = get_settings()
        self.base_url = settings.parkings_url.rstrip("/")
        self.service_token = settings.reservations_service_token
        self.timeout = httpx.Timeout(
            connect=settings.parkings_connect_timeout_seconds,
            read=settings.parkings_read_timeout_seconds,
            write=settings.parkings_read_timeout_seconds,
            pool=settings.parkings_connect_timeout_seconds,
        )

    def assign(
        self,
        reservation_id: str,
        parking_id: str,
        spot_id: str,
        operation_id: str,
        correlation_id: str,
    ) -> ParkingResult:
        try:
            response = httpx.put(
                f"{self.base_url}/internal/v1/asignaciones/{reservation_id}",
                json={"parking_id": parking_id, "spot_id": spot_id, "operation_id": operation_id},
                headers={"X-Service-Token": self.service_token, "X-Correlation-ID": correlation_id},
                timeout=self.timeout,
            )
        except (httpx.TimeoutException, httpx.NetworkError):
            return ParkingResult("transient")
        return self._assignment_result(response)

    def release(self, reservation_id: str, operation_id: str, correlation_id: str) -> ParkingResult:
        try:
            response = httpx.delete(
                f"{self.base_url}/internal/v1/asignaciones/{reservation_id}",
                headers={
                    "X-Service-Token": self.service_token,
                    "X-Correlation-ID": correlation_id,
                    "Idempotency-Key": operation_id,
                },
                timeout=self.timeout,
            )
        except (httpx.TimeoutException, httpx.NetworkError):
            return ParkingResult("transient")
        if response.status_code == 200:
            try:
                if response.json().get("status") == "released":
                    return ParkingResult("released", response.status_code)
            except ValueError:
                pass
        if response.status_code >= 500:
            return ParkingResult("transient", response.status_code)
        return self._error_result(response)

    @staticmethod
    def _assignment_result(response: httpx.Response) -> ParkingResult:
        if response.status_code in {200, 201}:
            try:
                if response.json().get("status") == "assigned":
                    return ParkingResult("assigned", response.status_code)
            except ValueError:
                pass
        if response.status_code >= 500:
            return ParkingResult("transient", response.status_code)
        if response.status_code in {404, 409}:
            return ParkingClient._error_result(response)
        return ParkingResult("transient", response.status_code)

    @staticmethod
    def _error_result(response: httpx.Response) -> ParkingResult:
        try:
            error = response.json().get("error", {})
            return ParkingResult(
                "rejected",
                response.status_code,
                error.get("code") or "UPSTREAM_REJECTED",
                error.get("details", {}).get("reason"),
            )
        except ValueError:
            return ParkingResult("transient", response.status_code)


def get_parking_client() -> ParkingClient:
    return ParkingClient()

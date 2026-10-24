import httpx

from app.config import get_settings
from app.schemas import Recipient


class TransientRecipientError(RuntimeError):
    pass


class PermanentRecipientError(RuntimeError):
    pass


class RecipientClient:
    def __init__(self) -> None:
        settings = get_settings()
        self.base_url = settings.usuarios_url.rstrip("/")
        self.token = settings.notifications_service_token
        self.timeout = httpx.Timeout(connect=settings.usuarios_connect_timeout_seconds,
                                     read=settings.usuarios_read_timeout_seconds,
                                     write=settings.usuarios_read_timeout_seconds,
                                     pool=settings.usuarios_connect_timeout_seconds)

    def get(self, user_id: str, correlation_id: str) -> Recipient:
        try:
            response = httpx.get(f"{self.base_url}/internal/v1/usuarios/{user_id}/destinatario",
                                 headers={"X-Service-Token": self.token, "X-Correlation-ID": correlation_id},
                                 timeout=self.timeout)
        except (httpx.TimeoutException, httpx.NetworkError) as exc:
            raise TransientRecipientError() from exc
        if response.status_code == 200:
            try:
                return Recipient.model_validate(response.json())
            except ValueError as exc:
                raise PermanentRecipientError() from exc
        if response.status_code == 404:
            raise PermanentRecipientError("usuario inexistente")
        raise TransientRecipientError(f"usuarios respondio {response.status_code}")

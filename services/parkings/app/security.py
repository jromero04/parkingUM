import hmac
from pathlib import Path
from typing import Annotated, Any

import jwt
from fastapi import Depends, Header
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import InvalidTokenError

from app.config import get_settings
from app.errors import ApiError


bearer = HTTPBearer(auto_error=False)


def authenticated_claims(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
) -> dict[str, Any]:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise ApiError(401, "UNAUTHORIZED", "Se requiere autenticacion.")
    settings = get_settings()
    try:
        public_key = Path(settings.jwt_public_key_path).read_text(encoding="utf-8")
        payload = jwt.decode(
            credentials.credentials,
            public_key,
            algorithms=["RS256"],
            issuer=settings.jwt_issuer,
            audience=settings.jwt_audience,
            options={"require": ["sub", "role", "iss", "aud", "iat", "exp"]},
        )
        if payload.get("role") != "user":
            raise ApiError(403, "FORBIDDEN", "El rol no tiene permiso para esta operacion.")
        return payload
    except ApiError:
        raise
    except (InvalidTokenError, OSError):
        raise ApiError(401, "UNAUTHORIZED", "El token no es valido.") from None


def require_reservations_service(
    supplied: Annotated[str | None, Header(alias="X-Service-Token")] = None,
) -> None:
    expected = get_settings().reservations_service_token
    if supplied is None or not hmac.compare_digest(supplied, expected):
        raise ApiError(403, "FORBIDDEN", "El servicio no tiene permiso para esta operacion.")

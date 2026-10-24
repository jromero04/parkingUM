from pathlib import Path
from typing import Annotated, Any
from uuid import UUID

import jwt
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import InvalidTokenError

from app.config import get_settings
from app.errors import ApiError


bearer = HTTPBearer(auto_error=False)


def require_admin(credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)]) -> dict[str, Any]:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise ApiError(401, "UNAUTHORIZED", "Se requiere autenticacion.")
    settings = get_settings()
    try:
        payload = jwt.decode(
            credentials.credentials,
            Path(settings.jwt_public_key_path).read_text(encoding="utf-8"),
            algorithms=["RS256"], issuer=settings.jwt_issuer, audience=settings.jwt_audience,
            options={"require": ["sub", "role", "iss", "aud", "iat", "exp"]},
        )
        payload["sub"] = str(UUID(payload["sub"]))
    except (InvalidTokenError, OSError, TypeError, ValueError):
        raise ApiError(401, "UNAUTHORIZED", "El token no es valido.") from None
    if payload.get("role") != "admin":
        raise ApiError(403, "FORBIDDEN", "Se requiere rol administrador.")
    return payload

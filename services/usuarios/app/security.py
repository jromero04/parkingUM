import hmac
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Annotated

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError
from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import InvalidTokenError
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.database import get_db
from app.errors import ApiError
from app.models import User

password_hasher = PasswordHasher()
bearer = HTTPBearer(auto_error=False)


def hash_password(password: str) -> str:
    return password_hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return password_hasher.verify(password_hash, password)
    except (VerifyMismatchError, InvalidHashError):
        return False


def create_access_token(user: User, settings: Settings) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user.id,
        "role": user.role,
        "iss": settings.jwt_issuer,
        "aud": settings.jwt_audience,
        "iat": now,
        "exp": now + timedelta(seconds=settings.jwt_expires_seconds),
    }
    private_key = Path(settings.jwt_private_key_path).read_text(encoding="utf-8")
    return jwt.encode(payload, private_key, algorithm="RS256")


def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> User:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise ApiError(401, "UNAUTHORIZED", "Se requiere autenticacion.")
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
    except (InvalidTokenError, OSError):
        raise ApiError(401, "UNAUTHORIZED", "Token invalido o vencido.") from None

    user = db.get(User, payload["sub"])
    if user is None or user.role != payload.get("role"):
        raise ApiError(401, "UNAUTHORIZED", "Token invalido o vencido.")
    return user


def require_notifications_service(
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
) -> None:
    supplied = request.headers.get("X-Service-Token", "")
    if not hmac.compare_digest(supplied, settings.notifications_service_token):
        raise ApiError(403, "FORBIDDEN", "Servicio sin permiso para esta operacion.")


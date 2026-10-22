from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.database import get_db
from app.errors import ApiError
from app.models import User
from app.schemas import LoginRequest, LoginResponse, RecipientRead, RegisterResponse, UserCreate, UserRead
from app.security import (
    create_access_token,
    get_current_user,
    hash_password,
    require_notifications_service,
    verify_password,
)

public_router = APIRouter(prefix="/api/v1/usuarios", tags=["usuarios"])
internal_router = APIRouter(prefix="/internal/v1/usuarios", tags=["interno"])
health_router = APIRouter(tags=["salud"])


@public_router.post("/registro", response_model=RegisterResponse, status_code=status.HTTP_201_CREATED)
def register(payload: UserCreate, db: Annotated[Session, Depends(get_db)]) -> RegisterResponse:
    user = User(name=payload.name, email=str(payload.email), password_hash=hash_password(payload.password))
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise ApiError(409, "EMAIL_ALREADY_EXISTS", "El email ya esta registrado.") from None
    db.refresh(user)
    return RegisterResponse(user=UserRead.model_validate(user))


@public_router.post("/login", response_model=LoginResponse)
def login(
    payload: LoginRequest,
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> LoginResponse:
    user = db.scalar(select(User).where(User.email == str(payload.email)))
    if user is None or not verify_password(payload.password, user.password_hash):
        raise ApiError(401, "INVALID_CREDENTIALS", "Email o contrasena incorrectos.")
    return LoginResponse(
        access_token=create_access_token(user, settings),
        expires_in=settings.jwt_expires_seconds,
        user=UserRead.model_validate(user),
    )


@public_router.get("/me", response_model=UserRead)
def me(user: Annotated[User, Depends(get_current_user)]) -> UserRead:
    return UserRead.model_validate(user)


@internal_router.get(
    "/{user_id}/destinatario",
    response_model=RecipientRead,
    dependencies=[Depends(require_notifications_service)],
)
def recipient(user_id: UUID, db: Annotated[Session, Depends(get_db)]) -> RecipientRead:
    user = db.get(User, str(user_id))
    if user is None:
        raise ApiError(404, "RESOURCE_NOT_FOUND", "Usuario inexistente.")
    return RecipientRead(user_id=user.id, email=user.email, name=user.name)


@health_router.get("/health/live")
def live() -> dict[str, str]:
    return {"status": "ok"}


@health_router.get("/health/ready")
def ready(db: Annotated[Session, Depends(get_db)]) -> dict[str, str]:
    try:
        db.execute(text("SELECT 1"))
    except SQLAlchemyError:
        raise ApiError(503, "SERVICE_UNAVAILABLE", "La base de datos no esta disponible.") from None
    return {"status": "ready"}


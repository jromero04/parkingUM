from pydantic import EmailStr, TypeAdapter, ValidationError
from sqlalchemy import select

from app.config import get_settings
from app.database import SessionLocal
from app.models import User
from app.security import hash_password


def main() -> None:
    settings = get_settings()
    values = (settings.admin_name, settings.admin_email, settings.admin_password)
    if not any(values):
        return
    if not all(values):
        raise RuntimeError("ADMIN_NAME, ADMIN_EMAIL y ADMIN_PASSWORD deben configurarse juntos")
    if settings.admin_name != settings.admin_name.strip() or not 1 <= len(settings.admin_name) <= 100:
        raise RuntimeError("ADMIN_NAME no cumple el contrato")
    if not 12 <= len(settings.admin_password) <= 128:
        raise RuntimeError("ADMIN_PASSWORD debe tener entre 12 y 128 caracteres")
    try:
        email = str(TypeAdapter(EmailStr).validate_python(settings.admin_email)).lower()
    except ValidationError as exc:
        raise RuntimeError("ADMIN_EMAIL no es valido") from exc

    with SessionLocal() as db:
        existing = db.scalar(select(User).where(User.email == email))
        if existing is not None:
            if existing.role != "admin":
                raise RuntimeError("ADMIN_EMAIL ya pertenece a un usuario sin rol admin")
            return
        db.add(
            User(
                name=settings.admin_name,
                email=email,
                password_hash=hash_password(settings.admin_password),
                role="admin",
            )
        )
        db.commit()


if __name__ == "__main__":
    main()

from pydantic import EmailStr, TypeAdapter, ValidationError
from sqlalchemy import select

from app.config import get_settings
from app.database import SessionLocal
from app.models import User
from app.security import hash_password


def main() -> None:
    settings = get_settings()
    values = (settings.sensor_name, settings.sensor_email, settings.sensor_password)
    if not any(values):
        return
    if not all(values):
        raise RuntimeError("SENSOR_NAME, SENSOR_EMAIL y SENSOR_PASSWORD deben configurarse juntos")
    if settings.sensor_name != settings.sensor_name.strip() or not 1 <= len(settings.sensor_name) <= 100:
        raise RuntimeError("SENSOR_NAME no cumple el contrato")
    if not 12 <= len(settings.sensor_password) <= 128:
        raise RuntimeError("SENSOR_PASSWORD debe tener entre 12 y 128 caracteres")
    try:
        email = str(TypeAdapter(EmailStr).validate_python(settings.sensor_email)).lower()
    except ValidationError as exc:
        raise RuntimeError("SENSOR_EMAIL no es valido") from exc

    with SessionLocal() as db:
        existing = db.scalar(select(User).where(User.email == email))
        if existing is not None:
            if existing.role != "sensor":
                raise RuntimeError("SENSOR_EMAIL ya pertenece a un usuario con otro rol")
            return
        db.add(
            User(
                name=settings.sensor_name,
                email=email,
                password_hash=hash_password(settings.sensor_password),
                role="sensor",
            )
        )
        db.commit()


if __name__ == "__main__":
    main()

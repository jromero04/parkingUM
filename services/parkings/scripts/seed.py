import uuid

from sqlalchemy import select

from app.database import SessionLocal
from app.models import Parking, Spot
from app.outbox import add_spot_event


PARKING_ID = "11111111-1111-4111-8111-111111111111"
SPOT_ID = "22222222-2222-4222-8222-222222222222"
SENSOR_ID = "33333333-3333-4333-8333-333333333333"


def main() -> None:
    with SessionLocal() as db:
        if db.scalar(select(Parking).where(Parking.id == PARKING_ID)) is not None:
            return
        parking = Parking(id=PARKING_ID, name="Parking Central", address="Av. Principal 1234")
        spot = Spot(id=SPOT_ID, parking_id=PARKING_ID, sensor_id=SENSOR_ID, label="A-01")
        db.add_all([parking, spot])
        db.flush()
        add_spot_event(db, spot, "parking.spot_initialized.v1", "initial_state", str(uuid.uuid4()))
        db.commit()


if __name__ == "__main__":
    main()

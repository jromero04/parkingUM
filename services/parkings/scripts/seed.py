import uuid

from app.catalog import PARKING_ID, configured_spots
from app.database import SessionLocal
from app.models import Parking, Spot
from app.outbox import add_spot_event


def main() -> None:
    with SessionLocal() as db:
        parking = db.get(Parking, PARKING_ID)
        if parking is None:
            parking = Parking(id=PARKING_ID)
            db.add(parking)
        parking.name = "Parking Central"
        parking.address = "Av. Dra. María Luisa Saldún de Rodriguez 2037"

        for definition in configured_spots():
            spot = db.get(Spot, definition["id"])
            if spot is None:
                spot = Spot(parking_id=PARKING_ID, **definition)
                db.add(spot)
                db.flush()
                add_spot_event(
                    db,
                    spot,
                    "parking.spot_initialized.v1",
                    "initial_state",
                    str(uuid.uuid4()),
                )
            else:
                spot.parking_id = PARKING_ID
                spot.sensor_id = definition["sensor_id"]
                spot.label = definition["label"]

        db.commit()


if __name__ == "__main__":
    main()

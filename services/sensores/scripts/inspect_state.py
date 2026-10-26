import argparse
from app.catalog import configured_sensors
from app.config import get_settings
from app.state import SensorState
parser=argparse.ArgumentParser(); parser.add_argument("--spot",default="A-01")
args=parser.parse_args(); settings=get_settings()
definition=next((item for item in configured_sensors() if item["label"]==args.spot.upper()),None)
if definition is None: raise SystemExit(f"Plaza desconocida: {args.spot}")
print(SensorState(settings.state_db_path,definition["sensor_id"],definition["spot_id"]).inspect())

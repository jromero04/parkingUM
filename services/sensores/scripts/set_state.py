import argparse
from app.config import get_settings
from app.state import SensorState
parser=argparse.ArgumentParser(); parser.add_argument("--occupied",choices=("true","false"),required=True)
args=parser.parse_args(); settings=get_settings()
state=SensorState(settings.state_db_path,settings.sensor_id,settings.spot_id)
state.set_occupied(args.occupied=="true")
print(state.inspect())

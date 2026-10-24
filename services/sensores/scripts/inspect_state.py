from app.config import get_settings
from app.state import SensorState
settings=get_settings(); print(SensorState(settings.state_db_path,settings.sensor_id,settings.spot_id).inspect())

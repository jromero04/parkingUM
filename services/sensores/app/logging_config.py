import json, logging, os, socket
from datetime import datetime, timezone


class JsonFormatter(logging.Formatter):
    def format(self, record):
        value={"timestamp":datetime.now(timezone.utc).isoformat().replace("+00:00","Z"),
               "level":record.levelname,"service":os.getenv("SERVICE_NAME","sensores"),
               "instance_id":os.getenv("HOSTNAME",socket.gethostname()),"action":getattr(record,"action","log"),
               "result":getattr(record,"result","info"),"correlation_id":getattr(record,"correlation_id",None)}
        for key in ("event_id","sensor_id","spot_id","sequence","attempt"):
            item=getattr(record,key,None)
            if item is not None: value[key]=item
        if record.getMessage(): value["message"]=record.getMessage()
        if record.exc_info: value["exception"]=self.formatException(record.exc_info)
        return json.dumps(value,separators=(",",":"),default=str)
def configure_logging():
    handler=logging.StreamHandler(); handler.setFormatter(JsonFormatter())
    root=logging.getLogger(); root.handlers.clear(); root.addHandler(handler); root.setLevel(logging.INFO)

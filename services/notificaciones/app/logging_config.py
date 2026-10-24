import json
import logging
import os
import socket
from datetime import datetime, timezone


STANDARD = {"name", "msg", "args", "levelname", "levelno", "pathname", "filename", "module", "exc_info",
            "exc_text", "stack_info", "lineno", "funcName", "created", "msecs", "relativeCreated", "thread",
            "threadName", "processName", "process", "taskName"}


class JsonFormatter(logging.Formatter):
    def format(self, record):
        value = {"timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                 "level": record.levelname, "service": os.getenv("SERVICE_NAME", record.name),
                 "instance_id": os.getenv("HOSTNAME", socket.gethostname()),
                 "action": getattr(record, "action", "log"), "result": getattr(record, "result", "info"),
                 "correlation_id": getattr(record, "correlation_id", None)}
        for key, item in record.__dict__.items():
            if key not in STANDARD and key not in value and item is not None:
                value[key] = item
        if record.getMessage(): value["message"] = record.getMessage()
        if record.exc_info: value["exception"] = self.formatException(record.exc_info)
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"), default=str)


def configure_logging(name):
    os.environ["SERVICE_NAME"] = name
    handler = logging.StreamHandler(); handler.setFormatter(JsonFormatter())
    root = logging.getLogger(); root.handlers.clear(); root.addHandler(handler); root.setLevel(logging.INFO)


def log_event(logger, action, result, *, level=logging.INFO, correlation_id=None, **fields):
    logger.log(level, "", extra={"action": action, "result": result,
                                  "correlation_id": correlation_id, **fields})

import json
import logging
import os
import sys
import uuid
from logging.handlers import TimedRotatingFileHandler
from contextvars import ContextVar
from datetime import datetime

# Contexto para trazabilidad por request/ejecución
_request_id: ContextVar[str] = ContextVar("request_id", default=None)

def set_request_id(value: str | None = None) -> str:
    rid = value or str(uuid.uuid4())
    _request_id.set(rid)
    return rid

def get_request_id() -> str | None:
    return _request_id.get()

class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": datetime.utcfromtimestamp(record.created).isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
            "module": record.module,
            "func": record.funcName,
            "line": record.lineno,
            "request_id": get_request_id(),
        }
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        # Adjunta extras si existen
        for key in ("ticket_id", "stage", "extra"):
            if hasattr(record, key):
                payload[key] = getattr(record, key)
        return json.dumps(payload, ensure_ascii=False)

def _make_stream_handler(level: int) -> logging.Handler:
    h = logging.StreamHandler(sys.stdout)
    h.setLevel(level)
    h.setFormatter(JsonFormatter())
    return h

def _make_file_handler(log_path: str, level: int) -> logging.Handler:
    os.makedirs(os.path.dirname(log_path), exist_ok=True)
    h = TimedRotatingFileHandler(log_path, when="midnight", backupCount=7, encoding="utf-8")
    h.setLevel(level)
    h.setFormatter(JsonFormatter())
    return h

def get_logger(name: str = "app"):
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger  # ya configurado

    level_name = os.getenv("LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)
    log_path = os.getenv("LOG_PATH", "logs/app.log")

    logger.setLevel(level)
    logger.addHandler(_make_stream_handler(level))
    logger.addHandler(_make_file_handler(log_path, level))
    logger.propagate = False
    return logger

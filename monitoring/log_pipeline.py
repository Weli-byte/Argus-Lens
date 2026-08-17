import time
import json
import logging
import uuid
import sys
from typing import Any, Dict
from contextvars import ContextVar

# Correlation ID per request
correlation_id: ContextVar[str] = ContextVar("correlation_id", default="system")

class JSONLogFormatter(logging.Formatter):
    """
    Enterprise Structured JSON Logging formatter.
    Allows easy ingestion by ELK, Splunk, or Datadog.
    """
    def format(self, record: logging.LogRecord) -> str:
        log_obj = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "logger": record.name,
            "correlation_id": correlation_id.get(),
            "message": record.getMessage(),
            "module": record.module,
            "funcName": record.funcName,
            "lineNo": record.lineno,
        }
        
        if record.exc_info:
            log_obj["exception"] = self.formatException(record.exc_info)
            
        if hasattr(record, "extra_data"):
            log_obj["extra"] = record.extra_data

        return json.dumps(log_obj)

def setup_structured_logging():
    logger = logging.getLogger("arguslens")
    logger.setLevel(logging.INFO)
    
    # Prevent duplicated logs if setup is called multiple times
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(JSONLogFormatter())
        logger.addHandler(handler)
        
    return logger

logger = setup_structured_logging()

def set_correlation_id(cid: str = None) -> str:
    """Sets a unique ID for request tracing across microservices."""
    if not cid:
        cid = str(uuid.uuid4())
    correlation_id.set(cid)
    return cid

import json
import logging
import os
import sys
from datetime import datetime, timezone
from typing import Any, Dict


class JSONFormatter(logging.Formatter):
    """
    Custom Logging Formatter that converts log records into structured JSON objects.
    This enables seamless parsing and log filtering in Grafana Loki via Promtail.
    """

    def format(self, record: logging.LogRecord) -> str:
        log_obj: Dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Include bot_id if available on the log record
        if hasattr(record, "bot_id"):
            log_obj["bot_id"] = getattr(record, "bot_id")

        if hasattr(record, "event_type"):
            log_obj["event_type"] = getattr(record, "event_type")

        if hasattr(record, "user_id"):
            log_obj["user_id"] = getattr(record, "user_id")

        # Include exception traceback if record contains exc_info
        if record.exc_info:
            log_obj["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_obj)


def setup_logging(default_level: int = logging.INFO, json_format: bool = True) -> None:
    """
    Configures root logging with either structured JSON formatting or human-readable format.
    Checks LOG_FORMAT env var (e.g. LOG_FORMAT=json or text).
    """
    log_format_env = os.getenv("LOG_FORMAT", "json" if json_format else "text").lower()
    root_logger = logging.getLogger()
    root_logger.setLevel(default_level)

    # Clear pre-existing handlers
    for h in root_logger.handlers[:]:
        root_logger.removeHandler(h)

    handler = logging.StreamHandler(sys.stdout)
    if log_format_env == "json":
        handler.setFormatter(JSONFormatter())
    else:
        handler.setFormatter(
            logging.Formatter("[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s")
        )

    root_logger.addHandler(handler)

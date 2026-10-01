from __future__ import annotations

import logging
import os
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path

from pydantic import BaseModel

LOG_FORMAT = "%(asctime)s %(name)s [%(levelname)s] - %(funcName)s - %(message)s"


def configure_logging(level: str, log_file: Path | None = None) -> None:
    """Send every logger to a single handler on the root logger, so the console or the log file
    (rotated every Monday, keeping the previous week) is written from one place."""
    handler: logging.Handler
    if log_file is None:
        handler = logging.StreamHandler()
    else:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        handler = TimedRotatingFileHandler(log_file, when="W0", backupCount=1)
    handler.setFormatter(logging.Formatter(LOG_FORMAT))

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(logging.WARNING)

    logging.getLogger("signalblast").setLevel(level)
    logging.getLogger("signalbot").setLevel(logging.WARNING)
    logging.getLogger("apscheduler").setLevel(logging.WARNING)


def route_signalbot_logs_to_root() -> None:
    """signalbot attaches its own console handler when a bot is created, drop it so
    its messages only reach the root handler set up in `configure_logging`."""
    logging.getLogger("signalbot").handlers.clear()


def get_data_path() -> Path:
    return Path(os.getenv("SIGNALBLAST_DATA_DIR", Path.home() / ".local/share/signalblast"))


class TimestampData(BaseModel):
    timestamp: int
    author: str
    broadcast_timestamps: dict[str, int]  # subscriber uuid, timestamp

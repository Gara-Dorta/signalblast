from logging import WARNING, Formatter, Logger, StreamHandler, getLogger
from logging.handlers import RotatingFileHandler
from pathlib import Path

from pydantic import BaseModel


def create_or_set_logger(name: str | None, logging_level: int = WARNING, log_file: Path | None = None) -> Logger:
    if log_file is None:
        # Log to console
        handler = StreamHandler()
    else:
        # Keep two files of max 5MB.
        handler = RotatingFileHandler(log_file, maxBytes=5 * 1024 * 1024, backupCount=1)

    formatter = Formatter("%(asctime)s %(name)s [%(levelname)s] - %(funcName)s - %(message)s")
    handler.setFormatter(formatter)

    logger = getLogger(name)
    logger.setLevel(logging_level)
    logger.addHandler(handler)
    return logger


def get_code_data_path() -> Path:
    return Path(__file__).parent.absolute() / "data"


class TimestampData(BaseModel):
    timestamp: int
    author: str
    broadcast_timestamps: dict[str, int]  # subscriber uuid, timestamp

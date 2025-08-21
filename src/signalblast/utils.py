from logging import Formatter, Logger, getLogger
from logging.handlers import RotatingFileHandler
from pathlib import Path

from pydantic import BaseModel


def _get_rotating_handler(log_file: Path) -> RotatingFileHandler:
    return RotatingFileHandler(str(log_file), mode="a", maxBytes=5 * 1024 * 1024, backupCount=1, encoding=None, delay=0)


def get_logger(name: str | None, log_file: Path, logging_level: int) -> Logger:
    handler = _get_rotating_handler(log_file)
    formatter = Formatter("%(asctime)s %(name)s [%(levelname)s] - %(funcName)s - %(message)s")
    handler.setFormatter(formatter)
    log = getLogger(name)
    log.setLevel(logging_level)
    log.addHandler(handler)
    return log


def redirect_semaphore_logger(log_file: str) -> None:
    formatter = Formatter("%(asctime)s %(name)s [%(levelname)s] - %(message)s")
    handler = _get_rotating_handler(log_file)
    handler.setFormatter(formatter)
    semaphore_log = getLogger("semaphore.bot")
    semaphore_log.addHandler(handler)


def get_code_data_path() -> Path:
    return Path(__file__).parent.absolute() / "data"


class TimestampData(BaseModel):
    timestamp: int
    author: str
    broadcast_timestamps: dict[str, int]  # subscriber uuid, timestamp

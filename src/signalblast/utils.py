import functools
from collections.abc import Callable
from logging import Formatter, Logger, getLogger
from logging.handlers import RotatingFileHandler
from pathlib import Path
from re import Pattern
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from signalbot import Context as ChatContext


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


def triggered(pattern: Pattern) -> Callable:
    def decorator_triggered(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper_triggered(*args, **kwargs) -> Callable:  # noqa: ANN002, ANN003
            c: ChatContext = args[1]
            text = c.message.text
            if not isinstance(text, str):
                return None

            if pattern.match(text) is None:
                return None

            return await func(*args, **kwargs)

        return wrapper_triggered

    return decorator_triggered

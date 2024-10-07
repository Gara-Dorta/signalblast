import functools
import pathlib
from logging import Formatter, Logger, getLogger
from logging.handlers import RotatingFileHandler
from re import Pattern
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from signalbot import Context as ChatContext


def _get_rotating_handler(log_file: str) -> RotatingFileHandler:
    return RotatingFileHandler(log_file, mode="a", maxBytes=5 * 1024 * 1024, backupCount=1, encoding=None, delay=0)


def get_logger(log_file: str, logging_level) -> Logger:
    handler = _get_rotating_handler(log_file)
    formatter = Formatter("%(asctime)s %(name)s [%(levelname)s] - %(funcName)s - %(message)s")
    handler.setLevel(logging_level)
    handler.setFormatter(formatter)
    log = getLogger("signalblast")
    log.addHandler(handler)
    return log


def redirect_semaphore_logger(log_file: str) -> None:
    formatter = Formatter("%(asctime)s %(name)s [%(levelname)s] - %(message)s")
    handler = _get_rotating_handler(log_file)
    handler.setFormatter(formatter)
    semaphore_log = getLogger("semaphore.bot")
    semaphore_log.addHandler(handler)


def get_code_data_path():
    return pathlib.Path(__file__).parent.absolute() / "data"


def triggered(pattern: Pattern):
    def decorator_triggered(func):
        @functools.wraps(func)
        async def wrapper_triggered(*args, **kwargs):
            c: ChatContext = args[1]
            text = c.message.text
            if not isinstance(text, str):
                return None

            if pattern.match(text) is None:
                return None

            return await func(*args, **kwargs)

        return wrapper_triggered

    return decorator_triggered

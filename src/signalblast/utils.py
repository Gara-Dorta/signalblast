from __future__ import annotations

import logging
import time
from logging.handlers import TimedRotatingFileHandler
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

LOG_FORMAT = "%(asctime)s %(name)s [%(levelname)s] - %(funcName)s - %(message)s"
SNIPPET_LENGTH = 40


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


def log_event(
    logger: logging.Logger,
    msg: str,
    *args: object,
    user: str,
    level: int = logging.INFO,
    exc_info: bool | BaseException | None = None,
) -> None:
    """Logs `msg` without saying who it is about, unless debug logging is on, then the uuid of `user` is added.
    `exc_info` is passed to `logger.log`."""
    if logger.isEnabledFor(logging.DEBUG):
        msg, args = msg + " (%s)", (*args, user)
    logger.log(level, msg, *args, exc_info=exc_info, stacklevel=2)


def now_ms() -> int:
    """The current time as a Signal timestamp."""
    return int(time.time() * 1000)


def people(count: int) -> str:
    return "1 person" if count == 1 else f"{count} people"


def snippet(text: str | None) -> str | None:
    """A short, single line preview of a message."""
    if not text:
        return None
    text = " ".join(text.split())
    return text if len(text) <= SNIPPET_LENGTH else text[:SNIPPET_LENGTH] + "…"

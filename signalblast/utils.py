from logging import getLogger, Formatter, Logger
from logging.handlers import RotatingFileHandler
import pathlib


def _get_rotating_handler(log_file: str) -> RotatingFileHandler:
    return RotatingFileHandler(log_file, mode='a', maxBytes=5*1024*1024, backupCount=1, encoding=None, delay=0)


def get_logger(log_file: str, logging_level) -> Logger:
    handler = _get_rotating_handler(log_file)
    formatter = Formatter('%(asctime)s %(name)s [%(levelname)s] - %(funcName)s - %(message)s')
    handler.setLevel(logging_level)
    handler.setFormatter(formatter)
    log = getLogger('signalblast')
    log.addHandler(handler)
    return log


def redirect_semaphore_logger(log_file: str) -> None:
    formatter = Formatter('%(asctime)s %(name)s [%(levelname)s] - %(message)s')
    handler = _get_rotating_handler(log_file)
    handler.setFormatter(formatter)
    semaphore_log = getLogger('semaphore.bot')
    semaphore_log.addHandler(handler)


def get_code_data_path():
    return pathlib.Path(__file__).parent.absolute() / 'data' / 'signalblast'

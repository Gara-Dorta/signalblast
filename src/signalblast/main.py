#!/usr/bin/env python

import argparse
import asyncio
import logging
import os
from dataclasses import dataclass

from signalblast.broadcastbot import BroadcasBot
from signalblast.commands import (
    AddAdmin,
    BanSubscriber,
    Broadcast,
    DisplayHelp,
    LastMsgUserUuid,
    LiftBanSubscriber,
    MessageFromAdmin,
    MessageToAdmin,
    RemoveAdmin,
    SetPing,
    ShowVersion,
    Subscribe,
    UnsetPing,
    Unsubscribe,
)
from signalblast.health_check import health_check
from signalblast.log_rollover import rotate_logs_periodically
from signalblast.utils import create_or_set_logger, get_data_path

LOGGING_LEVEL = logging.INFO

# LOG_FILE_PATH = None # Log to console
LOG_FILE_PATH = get_data_path() / "signalblast.log"

create_or_set_logger("signalbot", logging.WARNING, LOG_FILE_PATH)
create_or_set_logger("apscheduler", logging.WARNING, LOG_FILE_PATH)


@dataclass
class BotSettings:
    signal_service: str
    phone_number: str
    admin_pass: str | None
    expiration_time: int
    welcome_message: str | None = None
    health_check_port: int = 15556
    health_check_receiver: str | None = None
    instructions_url: str | None = None


async def initialise_bot(settings: BotSettings) -> BroadcasBot:
    config = {
        "signal_service": settings.signal_service,
        "phone_number": settings.phone_number,
        "storage": {"type": "sqlite", "db": get_data_path() / "signalblast.db", "check_same_thread": False},
    }

    get_data_path().mkdir(parents=True, exist_ok=True)

    logger = create_or_set_logger("signalblast", LOGGING_LEVEL, LOG_FILE_PATH)

    bot = BroadcasBot(config)
    await bot.load_data(
        logger=logger,
        admin_pass=settings.admin_pass,
        expiration_time=settings.expiration_time,
        welcome_message=settings.welcome_message,
        instructions_url=settings.instructions_url,
    )
    bot.restore_ping()

    bot.signal_bot.register(Subscribe(bot=bot), groups=False)
    bot.signal_bot.register(Unsubscribe(bot=bot), groups=False)
    bot.signal_bot.register(Broadcast(bot=bot), groups=False)
    bot.signal_bot.register(DisplayHelp(bot=bot), groups=False)
    bot.signal_bot.register(AddAdmin(bot=bot), groups=False)
    bot.signal_bot.register(RemoveAdmin(bot=bot), groups=False)
    bot.signal_bot.register(BanSubscriber(bot=bot), groups=False)
    bot.signal_bot.register(LiftBanSubscriber(bot=bot), groups=False)
    bot.signal_bot.register(SetPing(bot=bot), contacts=False, groups=True)
    bot.signal_bot.register(UnsetPing(bot=bot), contacts=False, groups=True)
    bot.signal_bot.register(MessageToAdmin(bot=bot), groups=True)
    bot.signal_bot.register(MessageFromAdmin(bot=bot), groups=True)
    bot.signal_bot.register(LastMsgUserUuid(bot=bot), groups=True)
    bot.signal_bot.register(ShowVersion(bot=bot), groups=False)

    bot.scheduler.add_job(bot.delete_old_timestamps, "interval", days=1)

    if settings.health_check_receiver is not None:
        bot.health_check_task = asyncio.create_task(
            health_check(bot, settings.health_check_receiver, settings.health_check_port),
        )

    bot.log_rollover_task = asyncio.create_task(rotate_logs_periodically(bot))

    return bot


if __name__ == "__main__":
    four_weeks = 60 * 60 * 24 * 7 * 4  # Number of seconds in 4 weeks

    args_parser = argparse.ArgumentParser()
    # `or None`/`or <default>` (rather than `os.environ.get(key, default)`) so that a
    # variable present but left blank (e.g. an unfilled .env value passed through by
    # docker compose as an empty string) is treated the same as an unset variable.
    args_parser.add_argument(
        "--admin_pass",
        type=str,
        help="the password to add or remove admins",
        default=os.environ.get("SIGNALBLAST_PASSWORD") or None,
    )
    args_parser.add_argument(
        "--expiration_time",
        type=int,
        default=os.environ.get("SIGNALBLAST_EXPIRATION_TIME") or four_weeks,
        help="the expiration time for the chats in seconds",
    )

    args_parser.add_argument(
        "--signal_service",
        type=str,
        default=os.environ.get("SIGNAL_SERVICE") or "localhost:8080",
        help="the address of the signal cli rest api",
    )

    args_parser.add_argument(
        "--phone_number",
        type=str,
        default=os.environ.get("SIGNALBLAST_PHONE_NUMBER") or None,
        help="the phone number of the bot",
    )

    args_parser.add_argument(
        "--welcome_message",
        type=str,
        default=os.environ.get("SIGNALBLAST_WELCOME_MESSAGE") or None,
        help="the initial message that the user receives",
    )

    args_parser.add_argument(
        "--health_check_port",
        type=int,
        default=os.environ.get("SIGNALBLAST_HEALTHCHECK_PORT") or "15556",
        help="the port that will be listening for health checks requests",
    )

    args_parser.add_argument(
        "--health_check_receiver",
        type=str,
        default=os.environ.get("SIGNALBLAST_HEALTHCHECK_RECEIVER") or None,
        help="the contact or group to send messages for health checks",
    )

    args_parser.add_argument(
        "--instructions_url",
        type=str,
        default=os.environ.get("SIGNALBLAST_INSTRUCTIONS_URL") or None,
        help="URL for the help message",
    )

    args = args_parser.parse_args()

    if args.phone_number is None:
        value_error_msg = "The bot phone number is not set"
        raise ValueError(value_error_msg)

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    bot = loop.run_until_complete(
        initialise_bot(
            BotSettings(
                signal_service=args.signal_service,
                phone_number=args.phone_number,
                admin_pass=args.admin_pass,
                expiration_time=args.expiration_time,
                welcome_message=args.welcome_message,
                health_check_port=args.health_check_port,
                health_check_receiver=args.health_check_receiver,
                instructions_url=args.instructions_url,
            ),
        ),
    )
    bot.start()

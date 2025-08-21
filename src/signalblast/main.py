#!/usr/bin/env python

import argparse
import asyncio
import logging
import os
from pathlib import Path

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
    Subscribe,
    UnsetPing,
    Unsubscribe,
)
from signalblast.health_check import health_check
from signalblast.utils import get_code_data_path, get_logger

LOGGING_LEVEL = logging.WARNING
LOG_TO_FILE = False
if LOG_TO_FILE:
    get_logger(None, Path("signalbot.log"), LOGGING_LEVEL)
else:
    logging.getLogger().setLevel(LOGGING_LEVEL)

logging.getLogger("apscheduler").setLevel(LOGGING_LEVEL)


async def initialise_bot(  # noqa: PLR0913 Too many arguments in function definition
    signal_service: str,
    phone_number: str,
    admin_pass: str,
    expiration_time: int,
    welcome_message: str | None = None,
    health_check_port: int = 15556,
    health_check_receiver: str | None = None,
    instructions_url: str | None = None,
) -> BroadcasBot:
    config = {
        "signal_service": signal_service,
        "phone_number": phone_number,
        "storage": {"type": "sqlite", "sqlite_db": "signalblast.db", "check_same_thread": False},
    }

    get_code_data_path().mkdir(parents=True, exist_ok=True)
    if LOG_TO_FILE:
        logger = get_logger("signalblast", Path("signalblast.log"), LOGGING_LEVEL)
    else:
        logger = logging.getLogger("signalblast")
        logger.setLevel(LOGGING_LEVEL)

    bot = BroadcasBot(config)
    await bot.load_data(
        logger=logger,
        admin_pass=admin_pass,
        expiration_time=expiration_time,
        welcome_message=welcome_message,
        instructions_url=instructions_url,
    )

    bot.register(Subscribe(bot=bot))
    bot.register(Unsubscribe(bot=bot))
    bot.register(Broadcast(bot=bot))
    bot.register(DisplayHelp(bot=bot))
    bot.register(AddAdmin(bot=bot))
    bot.register(RemoveAdmin(bot=bot))
    bot.register(BanSubscriber(bot=bot))
    bot.register(LiftBanSubscriber(bot=bot))
    bot.register(SetPing(bot=bot), contacts=False, groups=True)
    bot.register(UnsetPing(bot=bot), contacts=False, groups=True)
    bot.register(MessageToAdmin(bot=bot))
    bot.register(MessageFromAdmin(bot=bot))
    bot.register(LastMsgUserUuid(bot=bot))

    bot.scheduler.add_job(bot.delete_old_timestamps, "interval", days=1)

    if health_check_receiver is not None:
        bot.health_check_task = asyncio.create_task(health_check(bot, health_check_receiver, health_check_port))

    return bot


if __name__ == "__main__":
    four_weeks = 60 * 60 * 24 * 7 * 4  # Number of seconds in 4 weeks

    args_parser = argparse.ArgumentParser()
    args_parser.add_argument(
        "--admin_pass",
        type=str,
        help="the password to add or remove admins",
        default=os.environ.get("SIGNALBLAST_PASSWORD"),
    )
    args_parser.add_argument(
        "--expiration_time",
        type=int,
        default=os.environ.get("SIGNALBLAST_EXPIRATION_TIME", four_weeks),
        help="the expiration time for the chats in seconds",
    )

    args_parser.add_argument(
        "--signal_service",
        type=str,
        default=os.environ.get("SIGNAL_SERVICE", "localhost:8080"),
        help="the address of the signal cli rest api",
    )

    args_parser.add_argument(
        "--phone_number",
        type=str,
        default=os.environ.get("SIGNALBLAST_PHONE_NUMBER"),
        help="the phone number of the bot",
    )

    args_parser.add_argument(
        "--welcome_message",
        type=str,
        default=os.environ.get("SIGNALBLAST_WELCOME_MESSAGE"),
        help="the initial message that the user receives",
    )

    args_parser.add_argument(
        "--health_check_port",
        type=int,
        default=os.environ.get("SIGNALBLAST_HEALTHCHECK_PORT", "15556"),
        help="the port that will be listening for health checks requests",
    )

    args_parser.add_argument(
        "--health_check_receiver",
        type=str,
        default=os.environ.get("SIGNALBLAST_HEALTHCHECK_RECEIVER"),
        help="the contact or group to send messages for health checks",
    )

    args_parser.add_argument(
        "--instructions_url",
        type=str,
        default=os.environ.get("SIGNALBLAST_INSTRUCTIONS_URL"),
        help="URL for the help message",
    )

    args = args_parser.parse_args()

    if args.phone_number is None:
        value_error_msg = "The bot phone number is not set"
        raise ValueError(value_error_msg)

    loop = asyncio.get_event_loop()
    bot = loop.run_until_complete(
        initialise_bot(
            signal_service=args.signal_service,
            phone_number=args.phone_number,
            admin_pass=args.admin_pass,
            expiration_time=args.expiration_time,
            welcome_message=args.welcome_message,
            health_check_port=args.health_check_port,
            health_check_receiver=args.health_check_receiver,
            instructions_url=args.instructions_url,
        ),
    )
    bot.start()

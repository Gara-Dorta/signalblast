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
    LiftBanSubscriber,
    MessageFromAdmin,
    MessageToAdmin,
    RemoveAdmin,
    SetPing,
    Subscribe,
    UnsetPing,
    Unsubscribe,
)
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
    signal_data_path: Path,
    welcome_message: str | None = None,
    storage: dict[str, str] | None = None,
) -> BroadcasBot:
    config = {
        "signal_service": signal_service,
        "phone_number": phone_number,
        "storage": storage,
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
        signal_data_path=signal_data_path,
        welcome_message=welcome_message,
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
    return bot


if __name__ == "__main__":
    one_week = 60 * 60 * 24 * 7  # Number of seconds in a week

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
        default=os.environ.get("SIGNALBLAST_EXPIRATION_TIME", one_week),
        help="the expiration time for the chats in seconds",
    )
    args_parser.add_argument(
        "--signal_data_path",
        type=Path,
        default=os.environ.get("SIGNAL_DATA_PATH", Path.home() / (".local/share/signal-api/")),
        help="the path to the folder containig the signal api data",
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

    args = args_parser.parse_args()

    if args.phone_number is None:
        value_error_msg = "The bot phone number is not set"
        raise ValueError(value_error_msg)

    loop = asyncio.get_event_loop()
    bot = loop.run_until_complete(
        initialise_bot(
            signal_service=args.signal_service,
            phone_number=args.phone_number,
            signal_data_path=args.signal_data_path,
            admin_pass=args.admin_pass,
            expiration_time=args.expiration_time,
            welcome_message=args.welcome_message,
        ),
    )
    bot.start()

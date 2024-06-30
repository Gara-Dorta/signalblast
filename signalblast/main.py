#!/usr/bin/env python

import argparse
import asyncio
import logging
import os
from pathlib import Path
from typing import Optional

from signalblast.bot_answers import (
    AddAdmin,
    BanSubscriber,
    BroadcasBot,
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
from signalblast.utils import get_code_data_path

logging.getLogger().setLevel(logging.WARNING)
logging.getLogger("apscheduler").setLevel(logging.WARNING)


async def initialise_bot(
    signal_service: str,
    phone_number: str,
    admin_pass: str,
    expiration_time: int,
    signal_data_path: Path,
    storage: Optional[dict[str, str]] = None,
) -> BroadcasBot:
    config = {
        "signal_service": signal_service,
        "phone_number": phone_number,
        "storage": storage,
    }

    get_code_data_path().mkdir(parents=True, exist_ok=True)

    bot = BroadcasBot(config)
    await bot.load_data(
        logger=logging.getLogger("signalblast"),
        admin_pass=admin_pass,
        expiration_time=expiration_time,
        signal_data_path=signal_data_path,
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

    args = args_parser.parse_args()

    if args.phone_number is None:
        raise ValueError("The bot phone number is not set")

    if args.admin_pass is None:
        raise ValueError("The bot admin password is not set")

    loop = asyncio.get_event_loop()
    bot = loop.run_until_complete(
        initialise_bot(
            signal_service=args.signal_service,
            phone_number=args.phone_number,
            signal_data_path=args.signal_data_path,
            admin_pass=args.admin_pass,
            expiration_time=args.expiration_time,
        )
    )
    bot.start()

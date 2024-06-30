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
    storage: Optional[str] = None,
) -> BroadcasBot:
    config = {
        "signal_service": signal_service,
        "phone_number": phone_number,
        "storage": None,
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
    default_expiration_time = 60 * 60 * 24 * 7  # Number of seconds in a week
    if os.environ.get("SIGNALBLAST_EXPIRATION_TIME") is not None:
        default_expiration_time = os.environ["SIGNALBLAST_EXPIRATION_TIME"]

    args_parser = argparse.ArgumentParser()
    args_parser.add_argument(
        "--admin_pass",
        type=str,
        help="the password to add or remove admins",
        default=os.environ.get("SIGNALBLAST_PASSWORD"),
    )
    args_parser.add_argument(
        "--expiration_time", type=int, default=default_expiration_time, help="the expiration time for the chats"
    )
    args_parser.add_argument(
        "--signald_data_path",
        type=Path,
        default=Path("/home/user/signald"),
        help="the path to the folder containig the signald socket",
    )

    signal_service = os.environ.get("SIGNAL_SERVICE", "localhost:8080")

    phone_number = os.environ.get("PHONE_NUMBER", "+31000000000")

    args = args_parser.parse_args()

    loop = asyncio.get_event_loop()
    bot = loop.run_until_complete(initialise_bot(signal_service, phone_number, args.admin_pass, args.expiration_time))
    bot.start()

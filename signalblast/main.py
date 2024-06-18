#!/usr/bin/env python

import argparse
import os
from typing import Optional
from pathlib import Path
import os
from signalbot import SignalBot
import logging
import asyncio
from utils import get_code_data_path
logging.getLogger().setLevel(logging.INFO)
logging.getLogger("apscheduler").setLevel(logging.WARNING)

from bot_answers import BotAnswers, Subscribe, Unsubscribe, SetPing, UnsetPing, AddAdmin, RemoveAdmin, BanSubscriber, LiftBanSubscriber, Broadcast, DisplayHelp, MessageToAdmin, MessageFromAdmin
           

async def initialise_bot(signal_service: str, phone_number: str, storage: Optional[str] = None) -> BotAnswers:
    config = {
        "signal_service": signal_service,
        "phone_number": phone_number,
        "storage": None,
    }

    get_code_data_path().mkdir(parents=True, exist_ok=True)

    bot = BotAnswers(config)
    await bot.load_data(
               logger=logging.getLogger("signalblast"),
               admin_pass="123",
               expiration_time="5",
               signald_data_path=Path.home() / (".local/share/signal-api/"))
    
    bot.register(Subscribe(bot=bot))
    bot.register(Unsubscribe(bot=bot))
    bot.register(Broadcast(bot=bot))
    bot.register(DisplayHelp(bot=bot))
    bot.register(AddAdmin(bot=bot))
    return bot
    

if __name__ == '__main__':
    default_expiration_time = 60 * 60 * 24 * 7  # Number of seconds in a week
    if os.environ.get("SIGNALBLAST_EXPIRATION_TIME") is not None:
        default_expiration_time = os.environ["SIGNALBLAST_EXPIRATION_TIME"]

    args_parser = argparse.ArgumentParser()
    args_parser.add_argument("--admin_pass", type=str, help="the password to add or remove admins",
                             default=os.environ.get("SIGNALBLAST_PASSWORD"))
    args_parser.add_argument("--expiration_time", type=int, default=default_expiration_time,
                             help="the expiration time for the chats")
    args_parser.add_argument("--signald_data_path", type=Path,
                             default=Path("/home/user/signald"),
                             help="the path to the folder containig the signald socket")

    signal_service = os.environ.get("SIGNAL_SERVICE", "localhost:8080")
    
    phone_number = os.environ.get("PHONE_NUMBER", "+31000000000")

    args = args_parser.parse_args()

    loop = asyncio.get_event_loop()
    bot = loop.run_until_complete(initialise_bot(signal_service, phone_number))
    bot.start()

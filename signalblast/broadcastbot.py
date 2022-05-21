#!/usr/bin/env python

import argparse
import anyio
import os
from semaphore import Bot
from logging import INFO
from typing import Optional
from pathlib import Path


from bot_answers import BotAnswers
from bot_commands import CommandRegex
from utils import get_logger, redirect_semaphore_logger, get_code_data_path


async def main(admin_pass: Optional[str], expiration_time: Optional[int], signald_data_path: Path):
    """Start the bot."""

    log_file = get_code_data_path() / 'signalblast.log' 
    logger = get_logger(log_file, logging_level=INFO)
    redirect_semaphore_logger(log_file)

    os.makedirs(get_code_data_path(), exist_ok=True)

    socket_path = signald_data_path / 'signald.sock'

    # Connect the bot to number.
    async with Bot(os.environ["SIGNAL_PHONE_NUMBER"], logging_level=INFO,
                   socket_path=socket_path) as bot:
        bot_answers = await BotAnswers.create(logger, admin_pass, expiration_time, signald_data_path)

        bot.register_handler(CommandRegex.subscribe, bot_answers.subscribe)
        bot.register_handler(CommandRegex.unsubscribe, bot_answers.unsubscribe)
        bot.register_handler(CommandRegex.broadcast, bot_answers.broadcast)
        bot.register_handler(CommandRegex.add_admin, bot_answers.add_admin)
        bot.register_handler(CommandRegex.remove_admin, bot_answers.remove_admin)
        bot.register_handler(CommandRegex.msg_to_admin, bot_answers.msg_to_admin)
        bot.register_handler(CommandRegex.msg_from_admin, bot_answers.msg_from_admin)
        bot.register_handler(CommandRegex.ban_subscriber, bot_answers.ban_user)
        bot.register_handler(CommandRegex.lift_ban_subscriber, bot_answers.lift_ban_user)
        bot.register_handler(CommandRegex.set_ping, bot_answers.set_ping)
        bot.register_handler(CommandRegex.unset_ping, bot_answers.unset_ping)
        bot.register_handler(".*", bot_answers.display_help)

        # Run the bot until you press Ctrl-C.
        await bot.start()


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

    args = args_parser.parse_args()
    anyio.run(main, args.admin_pass, args.expiration_time, args.signald_data_path)

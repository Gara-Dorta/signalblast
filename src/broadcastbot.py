#!/usr/bin/env python
#
# This code is heavily based on
# https://github.com/lwesterhof/semaphore/blob/19b949d336a2dafbddd26325db21fba2ed74d292/examples/broadcastbot.py
# See there for authorship
#
import logging
from logging.handlers import RotatingFileHandler
import os
from semaphore import Bot

from bot_answers import BotAnswers
from bot_commands import CommandRegex


async def main():
    """Start the bot."""

    logFile = '/var/log/signalblast.log'

    logging.basicConfig()
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    handler = RotatingFileHandler(logFile, mode='a', maxBytes=5*1024*1024, backupCount=1, encoding=None, delay=0)
    handler.setLevel(logging.DEBUG)
    handler.setFormatter(formatter)
    log = logging.getLogger()
    log.addHandler(handler)

    # Connect the bot to number.
    async with Bot(os.environ["SIGNAL_PHONE_NUMBER"], logging_level=logging.ERROR) as bot:
        bot_answers = BotAnswers()

        bot.register_handler(CommandRegex.subscribe.value, bot_answers.subscribe)
        bot.register_handler(CommandRegex.unsubscribe.value, bot_answers.unsubscribe)
        bot.register_handler(CommandRegex.broadcast.value, bot_answers.broadcast)
        bot.register_handler(".*", bot_answers.display_help)

        # Run the bot until you press Ctrl-C.
        await bot.start()


if __name__ == '__main__':
    import anyio
    anyio.run(main)

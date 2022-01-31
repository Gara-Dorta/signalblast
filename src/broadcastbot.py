#!/usr/bin/env python
#
# This code is heavily based on
# https://github.com/lwesterhof/semaphore/blob/19b949d336a2dafbddd26325db21fba2ed74d292/examples/broadcastbot.py
# See there for authorship
#
import os
from semaphore import Bot

from bot_answers import BotAnswers
from bot_commands import CommandRegex


async def main():
    """Start the bot."""

    # Connect the bot to number.
    async with Bot(os.environ["SIGNAL_PHONE_NUMBER"]) as bot:
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

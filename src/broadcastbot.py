#!/usr/bin/env python
#
# This code is heavily based on
# https://github.com/lwesterhof/semaphore/blob/19b949d336a2dafbddd26325db21fba2ed74d292/examples/broadcastbot.py
# See there for authorship
#
"""
Signal Bot example, broadcast to all subscribers.
"""
import os
from time import time
from typing import Dict
from enum import Enum
import re

from semaphore import Bot, ChatContext

SUBSCRIBERS: Dict[str, float] = {}


class CommandStrings(Enum):
    subscribe = "!subscribe"
    unsubscribe = "!unsubscribe"
    broadcast = "!broadcast"


def begings_with(in_str):
    return "^(" + in_str.value + ")"


class CommandRegex(Enum):
    subscribe = re.compile(begings_with(CommandStrings.subscribe))
    unsubscribe = re.compile(begings_with(CommandStrings.unsubscribe))
    broadcast = re.compile(begings_with(CommandStrings.broadcast))


HELP_MESSAGE = f"I'm sorry, I didn't understand you but I understand the following commands:\n\n"
for command_str in CommandStrings:
    HELP_MESSAGE += "\t" + command_str.value + "\n"
HELP_MESSAGE += "\nPlease try again"


async def subscribe(ctx: ChatContext) -> None:
    try:
        if ctx.message.source.uuid in SUBSCRIBERS:
            await ctx.message.reply("Already subscribed!")
        else:
            SUBSCRIBERS[ctx.message.source.uuid] = time()
            await ctx.message.reply("Subscription successful!")
    except Exception:
        await ctx.message.reply("Could not subscribe!")


async def unsubscribe(ctx: ChatContext) -> None:
    try:
        if ctx.message.source.uuid in SUBSCRIBERS:
            del SUBSCRIBERS[ctx.message.source.uuid]
            await ctx.message.reply("Successfully unsubscribed!")
        else:
            await ctx.message.reply("Not subscribed!")
    except Exception:
        await ctx.message.reply("Could not unsubscribe!")


async def broadcast(ctx: ChatContext) -> None:
    await ctx.message.mark_read()
    message = ctx.message.get_body()[len("!broadcast"):].strip()

    # Broadcast message to all subscribers.
    for subscriber in SUBSCRIBERS:
        if await ctx.bot.send_message(subscriber, message):
            print(f"Message successfully sent to {subscriber}")
        else:
            print(f"Could not send message to {subscriber}")
            del SUBSCRIBERS[subscriber]


async def display_help(ctx: ChatContext) -> None:
    message = ctx.message.get_body()
    for regex in CommandRegex:
        if regex.value.search(message) is not None:
            return

    await ctx.bot.send_message(ctx.message.source.uuid, HELP_MESSAGE)


async def main():
    """Start the bot."""
    # Connect the bot to number.
    async with Bot(os.environ["SIGNAL_PHONE_NUMBER"]) as bot:
        bot.register_handler(CommandRegex.subscribe.value, subscribe)
        bot.register_handler(CommandRegex.unsubscribe.value, unsubscribe)
        bot.register_handler(CommandRegex.broadcast.value, broadcast)
        bot.register_handler(".*", display_help)

        # Run the bot until you press Ctrl-C.
        await bot.start()


if __name__ == '__main__':
    import anyio
    anyio.run(main)

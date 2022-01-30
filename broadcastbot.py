import os
from time import time
from typing import Dict

from semaphore import Bot, ChatContext

subscribers: Dict[str, float] = {}


async def subscribe(ctx: ChatContext) -> None:
    try:
        if ctx.message.source.uuid in subscribers:
            await ctx.message.reply("Already subscribed!")
        else:
            subscribers[ctx.message.source.uuid] = time()
            await ctx.message.reply("Subscription successful!")
    except Exception:
        await ctx.message.reply("Could not subscribe!")


async def unsubscribe(ctx: ChatContext) -> None:
    try:
        if ctx.message.source.uuid in subscribers:
            del subscribers[ctx.message.source.uuid]
            await ctx.message.reply("Successfully unsubscribed!")
        else:
            await ctx.message.reply("Not subscribed!")
    except Exception:
        await ctx.message.reply("Could not unsubscribe!")


async def broadcast(ctx: ChatContext) -> None:
    await ctx.message.mark_read()
    message = ctx.message.get_body()[len("!broadcast"):].strip()

    # Broadcast message to all subscribers.
    for subscriber in subscribers:
        if await ctx.bot.send_message(subscriber, message):
            print(f"Message successfully sent to {subscriber}")
        else:
            print(f"Could not send message to {subscriber}")
            del subscribers[subscriber]


async def main():
    """Start the bot."""
    # Connect the bot to number.
    async with Bot(os.environ["SIGNAL_PHONE_NUMBER"]) as bot:
        bot.register_handler("!subscribe", subscribe)
        bot.register_handler("!unsubscribe", unsubscribe)
        bot.register_handler("!broadcast", broadcast)

        # Run the bot until you press Ctrl-C.
        await bot.start()


if __name__ == '__main__':
    import anyio
    anyio.run(main)

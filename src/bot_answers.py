from semaphore import ChatContext

from subscribers import Subscribers
from bot_commands import CommandStrings, CommandRegex


class BotAnswers():
    def __init__(self) -> None:
        self.subscribers = Subscribers.load_subscribers()
        self.help_message = self.compose_help_message()

    def compose_help_message(self):
        help_message = "I'm sorry, I didn't understand you but I understand the following commands:\n\n"
        for command_str in CommandStrings:
            help_message += "\t" + command_str.value + "\n"
        help_message += "\nPlease try again"
        return help_message

    async def subscribe(self, ctx: ChatContext) -> None:
        try:
            if ctx.message.source.uuid in self.subscribers:
                await ctx.message.reply("Already subscribed!")
            else:
                await self.subscribers.add(ctx.message.source.uuid)
                await ctx.message.reply("Subscription successful!")
        except Exception as e:
            await ctx.message.reply("Could not subscribe!")
            print(e)

    async def unsubscribe(self, ctx: ChatContext) -> None:
        try:
            if ctx.message.source.uuid in self.subscribers:
                await self.subscribers.remove(ctx.message.source.uuid)
                await ctx.message.reply("Successfully unsubscribed!")
            else:
                await ctx.message.reply("Not subscribed!")
        except Exception as e:
            await ctx.message.reply("Could not unsubscribe!")
            print(e)

    async def broadcast(self, ctx: ChatContext) -> None:
        num_broadcasts = 0
        num_subscribers = -1

        try:
            num_subscribers = len(self.subscribers)

            await ctx.message.mark_read()
            message = ctx.message.get_body()[len("!broadcast"):].strip()

            # Broadcast message to all subscribers.
            for subscriber in self.subscribers:
                if await ctx.bot.send_message(subscriber, message):
                    num_broadcasts += 1
                    raise ValueError("Bla")
                else:
                    print(f"Could not send message to {subscriber}")
                    await self.subscribers.remove(ctx.message.source.uuid)
        except Exception as e:
            error_str = "Something went wrong, could only send the message to "\
                        f"{num_broadcasts} out of {num_subscribers} subscribers"
            await ctx.message.reply(error_str)
            print(e)

    async def display_help(self, ctx: ChatContext) -> None:
        message = ctx.message.get_body()
        for regex in CommandRegex:
            if regex.value.search(message) is not None:
                return

        await ctx.bot.send_message(ctx.message.source.uuid, self.help_message)

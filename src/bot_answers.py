from semaphore import ChatContext
from logging import Logger

from subscribers import Subscribers
from bot_commands import CommandRegex
from message_handler import MessageHandler


class BotAnswers():
    def __init__(self, logger: Logger) -> None:
        self.subscribers = Subscribers.load_subscribers()
        self.message_handler = MessageHandler()

        self.help_message = self.message_handler.compose_help_message()
        self.must_subscribe_message = self.message_handler.compose_must_subscribe_message()

        self.logger = logger

    async def reply_with_fail_log(self, ctx, message) -> bool:
        if await ctx.message.reply(message):
            return True
        else:
            self.logger.warning(f"Could not send message to {ctx.message.source.uuid}")
            return False

    async def subscribe(self, ctx: ChatContext) -> None:
        try:
            if ctx.message.source.uuid in self.subscribers:
                await self.reply_with_fail_log(ctx, "Already subscribed!")
                self.logger.info("Already subscribed!")
            else:
                await self.subscribers.add(ctx.message.source.uuid)
                await self.reply_with_fail_log(ctx, "Subscription successful!")
        except Exception as e:
            self.logger.error(e, exc_info=True)
            try:
                await self.reply_with_fail_log(ctx, "Could not subscribe!")
            except Exception as e:
                self.logger.error(e, exc_info=True)

    async def unsubscribe(self, ctx: ChatContext) -> None:
        try:
            if ctx.message.source.uuid in self.subscribers:
                await self.subscribers.remove(ctx.message.source.uuid)
                await self.reply_with_fail_log(ctx, "Successfully unsubscribed!")
            else:
                await self.reply_with_fail_log(ctx, "Not subscribed!")
        except Exception as e:
            self.logger.error(e, exc_info=True)
            try:
                await self.reply_with_fail_log(ctx, "Could not unsubscribe!")
            except Exception as e:
                self.logger.error(e, exc_info=True)

    async def broadcast(self, ctx: ChatContext) -> None:
        num_broadcasts = 0
        num_subscribers = -1

        try:
            if ctx.message.source.uuid not in self.subscribers:
                await self.reply_with_fail_log(ctx.message.source.uuid, self.must_subscribe_message)
                return

            num_subscribers = len(self.subscribers)

            await ctx.message.mark_read()
            message = self.message_handler.prepare_message(ctx.message.get_body())
            attachments = self.message_handler.prepare_attachments(ctx.message.data_message.attachments)

            if message is None and attachments is None:
                return

            # Broadcast message to all subscribers.
            for subscriber in self.subscribers:
                if await ctx.bot.send_message(subscriber, message, attachments=attachments):
                    num_broadcasts += 1
                else:
                    self.logger.warning(f"Could not send message to {subscriber}")
                    await self.subscribers.remove(ctx.message.source.uuid)
        except Exception as e:
            self.logger.error(e, exc_info=True)
            try:
                error_str = "Something went wrong, could only send the message to "\
                            f"{num_broadcasts} out of {num_subscribers} subscribers"
                await self.reply_with_fail_log(ctx, error_str)
            except Exception as e:
                self.logger.error(e, exc_info=True)

    async def display_help(self, ctx: ChatContext) -> None:
        try:
            message = ctx.message.get_body()
            for regex in CommandRegex:
                if regex.value.search(message) is not None:
                    return

            if message == '':
                if ctx.message.data_message.attachments == []:
                    return  # This is a message emoticon reaction or a sticker, the bot can ignore these.

                # Only attachment, assume the user wants to forward that
                await self.broadcast(ctx)
            else:
                await self.reply_with_fail_log(ctx, self.help_message)
        except Exception as e:
            self.logger.error(e, exc_info=True)

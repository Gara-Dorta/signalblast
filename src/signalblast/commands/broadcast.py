import asyncio
import contextlib
from re import Pattern

from signalbot import Command
from signalbot import Context as ChatContext

from signalblast.broadcastbot import BroadcasBot
from signalblast.commands_strings import CommandRegex, PublicCommandStrings


class Broadcast(Command):
    def __init__(self, bot: BroadcasBot) -> None:
        super().__init__()
        self.broadcastbot = bot

    def is_valid_command(self, message: str, invalid_command: Pattern) -> bool:
        return any(regex != invalid_command and regex.search(message) is not None for regex in CommandRegex)

    @staticmethod
    async def check_send_tasks_results(send_tasks: list[asyncio.Task | None], bot: BroadcasBot) -> int:
        num_broadcasts = 0
        subscribers_to_remove: list[str] = []
        for send_task, subscriber in zip(send_tasks, bot.subscribers, strict=False):
            if send_task is not None:
                if send_task.exception() is None:
                    num_broadcasts += 1
                    bot.logger.info("Message successfully sent to %s", subscriber)
                else:
                    bot.logger.warning("Could not send message to %s", subscriber)
                    subscribers_to_remove.append(subscriber)

        for subscriber in subscribers_to_remove:
            await bot.subscribers.remove(subscriber)
            remove_message = "The bot is having problems sending you messages. "
            remove_message += "You have been removed from the list. "
            remove_message += "Please update signal, remove old linked devices and try subscribing again"
            with contextlib.suppress(Exception):
                # Most likely will fail to send the message but try anyway
                await bot.send(subscriber, remove_message)

        return num_broadcasts

    @staticmethod
    async def broadcast(bot: BroadcasBot, ctx: ChatContext) -> None:
        num_broadcasts = 0
        num_subscribers = -1
        attachments_deleted = False
        send_tasks_checked = False
        send_tasks: list[asyncio.Task | None] = []

        try:
            subscriber_uuid = ctx.message.source_uuid
            if subscriber_uuid in bot.banned_users:
                await bot.send(subscriber_uuid, "This number is not allowed to broadcast messages")
                bot.logger.info("%s tried to broadcast but they are banned", subscriber_uuid)
                return

            if subscriber_uuid not in bot.subscribers:
                await bot.send(subscriber_uuid, bot.must_subscribe_message)
                bot.logger.info("%s tried to broadcast but they are not subscribed", subscriber_uuid)
                return

            num_subscribers = len(bot.subscribers)

            # await ctx.message.mark_read()
            message = bot.message_handler.remove_command_from_message(ctx.message.text, PublicCommandStrings.broadcast)
            attachments = bot.message_handler.empty_list_to_none(ctx.message.base64_attachments)
            # link_previews = bot.message_handler.empty_list_to_none(ctx.message.data_message.previews)

            if message is None and attachments is None:
                return

            if message is None:
                message = ""

            # Broadcast message to all subscribers.
            send_tasks: list[asyncio.Task | None] = [None] * num_subscribers

            for i, subscriber in enumerate(bot.subscribers):
                send_tasks[i] = asyncio.create_task(bot.send(subscriber, message, base64_attachments=attachments))
                await asyncio.sleep(2)  # Avoid rate limiting by waiting a few seconds between messages

            await asyncio.wait(send_tasks)

            num_broadcasts = await Broadcast.check_send_tasks_results(send_tasks, bot)
            send_tasks_checked = True

            attachments_filenames = bot.message_handler.empty_list_to_none(ctx.message.attachments_filenames)
            bot.message_handler.delete_attachments(attachments_filenames, link_previews=None)
            attachments_deleted = True

            await bot.reply_with_warn_on_failure(ctx, f"Message sent to {num_broadcasts - 1} people")
        except Exception:
            bot.logger.exception("")
            try:
                if send_tasks_checked is False:
                    num_broadcasts = await Broadcast.check_send_tasks_results(send_tasks, bot)

                error_str = "Something went wrong when sending the message"
                error_str += f", it was only sent to {num_broadcasts - 1} out of {num_subscribers - 1} people"
                error_str += ", please contact the admin if the problem persists"
                await bot.reply_with_warn_on_failure(ctx, error_str)

                if attachments_deleted is False:
                    attachments_filenames = bot.message_handler.empty_list_to_none(ctx.message.attachments_filenames)
                    bot.message_handler.delete_attachments(attachments_filenames, link_previews=None)
            except Exception:
                bot.logger.exception("")

    async def handle(self, ctx: ChatContext) -> None:
        message = ctx.message.text
        subscriber_uuid = ctx.message.source_uuid
        if message is None:
            if ctx.message.base64_attachments == []:
                self.broadcastbot.logger.info("Received reaction, sticker or similar from %s", subscriber_uuid)
                return

            # Only attachment, assume the user wants to forward that
            self.broadcastbot.logger.info("Received a file from %s, broadcasting!", subscriber_uuid)
            await Broadcast.broadcast(self.broadcastbot, ctx)
            return

        if self.is_valid_command(message, invalid_command=CommandRegex.broadcast):
            return

        # By default broadcast all the messages
        await Broadcast.broadcast(self.broadcastbot, ctx)

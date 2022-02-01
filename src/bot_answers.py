import logging
from typing import List, Optional
from semaphore import ChatContext, Attachment

from subscribers import Subscribers
from bot_commands import CommandStrings, CommandRegex


class BotAnswers():
    def __init__(self) -> None:
        self.subscribers = Subscribers.load_subscribers()
        self.help_message = self.compose_help_message()
        self.must_subscribe_message = self.compose_must_subscribe_message()

    def compose_help_message(self):
        message = "I'm sorry, I didn't understand you but I understand the following commands:\n\n"
        for command_str in CommandStrings:
            message += "\t" + command_str.value + "\n"
        message += "\nPlease try again"
        return message

    def compose_must_subscribe_message(self):
        message = "To be able to send messages you must be a subscriber too.\n"
        message += "Please subscribe by sending:\n"
        message += f"\t{CommandStrings.subscribe.value}\n"
        message += "and try again after that."
        return message

    async def subscribe(self, ctx: ChatContext) -> None:
        try:
            if ctx.message.source.uuid in self.subscribers:
                await ctx.message.reply("Already subscribed!")
            else:
                await self.subscribers.add(ctx.message.source.uuid)
                await ctx.message.reply("Subscription successful!")
        except Exception as e:
            logging.error(e, exc_info=True)
            try:
                await ctx.message.reply("Could not subscribe!")
            except Exception as e:
                logging.error(e, exc_info=True)

    async def unsubscribe(self, ctx: ChatContext) -> None:
        try:
            if ctx.message.source.uuid in self.subscribers:
                await self.subscribers.remove(ctx.message.source.uuid)
                await ctx.message.reply("Successfully unsubscribed!")
            else:
                await ctx.message.reply("Not subscribed!")
        except Exception as e:
            logging.error(e, exc_info=True)
            try:
                await ctx.message.reply("Could not unsubscribe!")
            except Exception as e:
                logging.error(e, exc_info=True)

    def prepare_attachments(self, attachments: Optional[List[Attachment]]) -> List:
        if attachments == []:
            return None

        attachments_to_send = []
        for attachment in attachments:
            attachment_to_send = {"filename": attachment.stored_filename,
                                  "width": attachment.width,
                                  "height": attachment.height,
                                  "contentType": attachment.content_type,
                                  }
            attachments_to_send.append(attachment_to_send)

        return attachments_to_send

    def prepare_message(self, message: str) -> str:
        if message == '':
            return None
        else:
            message = message[len("!broadcast"):].strip()
            if message == '':
                return None
            else:
                return message

    async def broadcast(self, ctx: ChatContext) -> None:
        num_broadcasts = 0
        num_subscribers = -1

        try:
            if ctx.message.source.uuid not in self.subscribers:
                await ctx.bot.send_message(ctx.message.source.uuid, self.must_subscribe_message)
                return

            num_subscribers = len(self.subscribers)

            await ctx.message.mark_read()
            message = self.prepare_message(ctx.message.get_body())
            attachments = self.prepare_attachments(ctx.message.data_message.attachments)

            if message is None and attachments is None:
                return

            # Broadcast message to all subscribers.
            for subscriber in self.subscribers:
                if await ctx.bot.send_message(subscriber, message, attachments=attachments):
                    num_broadcasts += 1
                else:
                    print(f"Could not send message to {subscriber}")
                    await self.subscribers.remove(ctx.message.source.uuid)
        except Exception as e:
            logging.error(e, exc_info=True)
            try:
                error_str = "Something went wrong, could only send the message to "\
                            f"{num_broadcasts} out of {num_subscribers} subscribers"
                await ctx.message.reply(error_str)
            except Exception as e:
                logging.error(e, exc_info=True)

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
                await ctx.bot.send_message(ctx.message.source.uuid, self.help_message)
        except Exception as e:
            logging.error(e, exc_info=True)

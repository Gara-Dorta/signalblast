from __future__ import annotations

from typing import TYPE_CHECKING

from signalbot import DataMessageHandler, ReceiptType, RemoteDeleteHandler

from signalblast.commands.broadcast.delete import BroadcastDeleter
from signalblast.commands.broadcast.delivery import DeliveryTracker
from signalblast.commands.broadcast.send import BroadcastSender
from signalblast.commands_strings import CommandRegex

if TYPE_CHECKING:
    from re import Pattern

    from signalbot import DataMessageContext, RemoteDeleteContext

    from signalblast.broadcastbot import BroadcasBot


class Broadcast(DataMessageHandler, RemoteDeleteHandler):
    def __init__(self, bot: BroadcasBot) -> None:
        super().__init__()
        self.broadcastbot = bot
        tracker = DeliveryTracker(bot)
        self._sender = BroadcastSender(bot, tracker)
        self._deleter = BroadcastDeleter(bot, tracker)

    def is_valid_command(self, message: str, invalid_command: Pattern) -> bool:
        return any(regex != invalid_command and regex.search(message) is not None for regex in CommandRegex)

    async def handle_data_message(self, context: DataMessageContext) -> None:
        message = context.message.text
        subscriber_uuid = context.message.source_uuid

        if message is None:
            if not context.message.attachments:
                self.broadcastbot.logger.info("Received reaction, sticker or similar from %s", subscriber_uuid)
                return

            await context.send_receipt(ReceiptType.READ)

            # Only attachment, assume the user wants to forward that
            self.broadcastbot.logger.info("Received a file from %s, broadcasting!", subscriber_uuid)
            await self._sender.send(context)
            return

        if self.is_valid_command(message, invalid_command=CommandRegex.broadcast):
            return

        await context.send_receipt(ReceiptType.READ)

        # By default broadcast all the messages
        await self._sender.send(context)

    async def handle_remote_delete(self, context: RemoteDeleteContext) -> None:
        await self._deleter.delete(context)

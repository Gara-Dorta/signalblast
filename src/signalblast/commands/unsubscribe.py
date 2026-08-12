from signalbot import DataMessageContext, DataMessageHandler, ReceiptType, regex_triggered

from signalblast.broadcastbot import BroadcasBot
from signalblast.commands_strings import CommandRegex


class Unsubscribe(DataMessageHandler):
    def __init__(self, bot: BroadcasBot) -> None:
        super().__init__()
        self.broadcastbot = bot

    @regex_triggered(CommandRegex.unsubscribe)
    async def handle_data_message(self, context: DataMessageContext) -> None:
        try:
            await context.send_receipt(ReceiptType.READ)

            subscriber_uuid = context.message.source_uuid

            if subscriber_uuid not in self.broadcastbot.subscribers:
                await self.broadcastbot.reply_with_warn_on_failure(context, "Not subscribed!")
                self.broadcastbot.logger.info("%s tried to unsubscribe but they are not subscribed", subscriber_uuid)
                return

            await self.broadcastbot.subscribers.remove(subscriber_uuid)
            await self.broadcastbot.reply_with_warn_on_failure(context, "Successfully unsubscribed!")
            self.broadcastbot.logger.info("%s unsubscribed", subscriber_uuid)
        except Exception:
            self.broadcastbot.logger.exception("")
            try:
                await self.broadcastbot.reply_with_warn_on_failure(context, "Could not unsubscribe!")
            except Exception:
                self.broadcastbot.logger.exception("")

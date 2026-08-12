from signalbot import DataMessageContext, DataMessageHandler, ReceiptType, SendMessage, regex_triggered

from signalblast.broadcastbot import BroadcasBot
from signalblast.commands_strings import AdminCommandStrings, CommandRegex


class UnsetPing(DataMessageHandler):
    def __init__(self, bot: BroadcasBot) -> None:
        super().__init__()
        self.broadcastbot = bot

    @regex_triggered(CommandRegex.unset_ping)
    async def handle_data_message(self, context: DataMessageContext) -> None:
        try:
            await context.send_receipt(ReceiptType.READ)

            if not await self.broadcastbot.is_user_admin(context, AdminCommandStrings.unset_ping):
                return

            if self.broadcastbot.ping_job is None:
                await context.reply(SendMessage(text="Cannot unset because ping was not set!"))
                return

            self.broadcastbot.clear_ping()
            await context.reply(SendMessage(text="Ping unset!"))
        except Exception:
            self.broadcastbot.logger.exception("")
            try:
                await self.broadcastbot.reply_with_warn_on_failure(context, "Failed to unset ping")
            except Exception:
                self.broadcastbot.logger.exception("")

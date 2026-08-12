from signalbot import DataMessageContext, DataMessageHandler, ReceiptType, SendMessage, regex_triggered

from signalblast.broadcastbot import BroadcasBot
from signalblast.commands_strings import AdminCommandStrings, CommandRegex


class LastMsgUserUuid(DataMessageHandler):
    def __init__(self, bot: BroadcasBot) -> None:
        super().__init__()
        self.broadcastbot = bot

    @regex_triggered(CommandRegex.last_msg_user_uuid)
    async def handle_data_message(self, context: DataMessageContext) -> None:
        try:
            await context.send_receipt(ReceiptType.READ)
            if not await self.broadcastbot.is_user_admin(context, AdminCommandStrings.last_msg_user_uuid):
                return
            msg = f"Last message was sent by\n\t{self.broadcastbot.last_msg_user_uuid}"
            await context.bot.messages.send(SendMessage(text=msg), self.broadcastbot.admin.admin_id)

            self.broadcastbot.logger.info(msg)
        except Exception:
            self.broadcastbot.logger.exception("")
            try:
                await self.broadcastbot.reply_with_warn_on_failure(context, "Failed get UUID")
            except Exception:
                self.broadcastbot.logger.exception("")

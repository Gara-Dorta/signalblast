from signalbot import DataMessageContext, DataMessageHandler, ReceiptType, SendMessage, regex_triggered

from signalblast.broadcastbot import BroadcasBot
from signalblast.commands_strings import AdminCommandStrings, CommandRegex


class MessageFromAdmin(DataMessageHandler):
    def __init__(self, bot: BroadcasBot) -> None:
        super().__init__()
        self.broadcastbot = bot

    @regex_triggered(CommandRegex.msg_from_admin)
    async def handle_data_message(self, context: DataMessageContext) -> None:
        try:
            await context.send_receipt(ReceiptType.READ)

            message = self.broadcastbot.message_handler.remove_command_from_message(
                context.message.text,
                AdminCommandStrings.msg_from_admin,
            )

            if not await self.broadcastbot.is_user_admin(context, AdminCommandStrings.msg_from_admin):
                return

            user_id, message = message.split(" ", 1)

            if user_id not in self.broadcastbot.subscribers:
                if " " in message:
                    confirmation, message = message.split(" ", 1)
                else:
                    confirmation = None
                if confirmation != "!force":
                    warn_message = "User is not in subscribers list, use !reply <uuid> !force to message them"
                    await self.broadcastbot.reply_with_warn_on_failure(context, warn_message)
                    return

            message = "Admin: " + message
            attachments = self.broadcastbot.message_handler.extract_base64_attachments(context.message.attachments)

            await context.bot.messages.send(SendMessage(text=message, base64_attachments=attachments), user_id)
            await self.broadcastbot.reply_with_warn_on_failure(context, "Message sent")
            self.broadcastbot.logger.info(
                "Sent message from admin %s to user %s",
                self.broadcastbot.admin.admin_id,
                user_id,
            )
        except Exception:
            self.broadcastbot.logger.exception("")
            try:
                await self.broadcastbot.reply_with_warn_on_failure(context, "Failed to send the message to the user!")
            except Exception:
                self.broadcastbot.logger.exception("")

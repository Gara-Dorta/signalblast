from __future__ import annotations

from typing import TYPE_CHECKING

from signalbot import DataMessageContext, DataMessageHandler, ReceiptType, SendMessage, regex_triggered

from signalblast.commands_strings import CommandRegex, PublicCommandStrings

if TYPE_CHECKING:
    from signalblast.broadcastbot import BroadcasBot


class MessageToAdmin(DataMessageHandler):
    def __init__(self, bot: BroadcasBot) -> None:
        super().__init__()
        self.broadcastbot = bot

    @regex_triggered(CommandRegex.msg_to_admin)
    async def handle_data_message(self, context: DataMessageContext) -> None:
        try:
            await context.send_receipt(ReceiptType.READ)

            subscriber_uuid = context.message.source_uuid
            message = self.broadcastbot.message_handler.remove_command_from_message(
                context.message.text,
                PublicCommandStrings.msg_to_admin,
            )

            if subscriber_uuid is None or message is None:
                self.broadcastbot.logger.warning("Received a message-to-admin with no source_uuid or text")
                return

            if self.broadcastbot.admin.admin_id is None:
                no_admin_msg = "I'm sorry but there are no admins to contact!"
                await self.broadcastbot.reply_with_warn_on_failure(context, no_admin_msg)
                self.broadcastbot.logger.info("Tried to contact an admin but there is none! %s", subscriber_uuid)
                return

            if subscriber_uuid in self.broadcastbot.banned_users:
                await self.broadcastbot.reply_with_warn_on_failure(context, "You are not allowed to contact the admin!")
                self.broadcastbot.logger.info("Banned user %s tried to contact admin", subscriber_uuid)
                return

            msg_to_admin = self.broadcastbot.message_handler.compose_message_to_admin(
                "Sent you message:\n",
                subscriber_uuid,
            )
            msg_to_admin += message
            attachments = self.broadcastbot.message_handler.extract_base64_attachments(context.message.attachments)
            await context.bot.messages.send(
                SendMessage(text=msg_to_admin, base64_attachments=attachments),
                self.broadcastbot.admin.admin_id,
            )
            await self.broadcastbot.reply_with_warn_on_failure(context, "Message sent to the admin")
            self.broadcastbot.logger.info(
                "Sent message from %s to admin %s",
                subscriber_uuid,
                self.broadcastbot.admin.admin_id,
            )
        except Exception:
            self.broadcastbot.logger.exception("")
            try:
                await self.broadcastbot.reply_with_warn_on_failure(context, "Failed to send the message to the admin!")
            except Exception:
                self.broadcastbot.logger.exception("")

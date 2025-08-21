from signalbot import Command, regex_triggered
from signalbot import Context as ChatContext

from signalblast.broadcastbot import BroadcasBot
from signalblast.commands_strings import CommandRegex, PublicCommandStrings


class MessageToAdmin(Command):
    def __init__(self, bot: BroadcasBot) -> None:
        super().__init__()
        self.broadcastbot = bot

    @regex_triggered(CommandRegex.msg_to_admin)
    async def handle(self, ctx: ChatContext) -> None:
        try:
            await ctx.receipt(receipt_type="read")

            subscriber_uuid = ctx.message.source_uuid
            message = self.broadcastbot.message_handler.remove_command_from_message(
                ctx.message.text,
                PublicCommandStrings.msg_to_admin,
            )

            if self.broadcastbot.admin.admin_id is None:
                await self.broadcastbot.reply_with_warn_on_failure(ctx, "I'm sorry but there are no admins to contact!")
                self.broadcastbot.logger.info("Tried to contact an admin but there is none! %s", subscriber_uuid)
                return

            if subscriber_uuid in self.broadcastbot.banned_users:
                await self.broadcastbot.reply_with_warn_on_failure(ctx, "You are not allowed to contact the admin!")
                self.broadcastbot.logger.info("Banned user %s tried to contact admin", subscriber_uuid)
                return

            msg_to_admin = self.broadcastbot.message_handler.compose_message_to_admin(
                "Sent you message:\n",
                subscriber_uuid,
            )
            msg_to_admin += message
            attachments = self.broadcastbot.message_handler.empty_list_to_none(ctx.message.base64_attachments)
            await self.broadcastbot.send(self.broadcastbot.admin.admin_id, msg_to_admin, base64_attachments=attachments)
            await self.broadcastbot.reply_with_warn_on_failure(ctx, "Message sent to the admin")
            self.broadcastbot.logger.info(
                "Sent message from %s to admin %s",
                subscriber_uuid,
                self.broadcastbot.admin.admin_id,
            )
        except Exception:
            self.broadcastbot.logger.exception("")
            try:
                await self.broadcastbot.reply_with_warn_on_failure(ctx, "Failed to send the message to the admin!")
            except Exception:
                self.broadcastbot.logger.exception("")

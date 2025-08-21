from signalbot import Command, regex_triggered
from signalbot import Context as ChatContext

from signalblast.broadcastbot import BroadcasBot
from signalblast.commands_strings import AdminCommandStrings, CommandRegex


class MessageFromAdmin(Command):
    def __init__(self, bot: BroadcasBot) -> None:
        super().__init__()
        self.broadcastbot = bot

    @regex_triggered(CommandRegex.msg_from_admin)
    async def handle(self, ctx: ChatContext) -> None:
        try:
            await ctx.receipt(receipt_type="read")

            message = self.broadcastbot.message_handler.remove_command_from_message(
                ctx.message.text,
                AdminCommandStrings.msg_from_admin,
            )

            if not await self.broadcastbot.is_user_admin(ctx, AdminCommandStrings.msg_from_admin):
                return

            user_id, message = message.split(" ", 1)

            if user_id not in self.broadcastbot.subscribers:
                if " " in message:
                    confirmation, message = message.split(" ", 1)
                else:
                    confirmation = None
                if confirmation != "!force":
                    warn_message = "User is not in subscribers list, use !reply <uuid> !force to message them"
                    await self.broadcastbot.reply_with_warn_on_failure(ctx, warn_message)
                    return

            message = "Admin: " + message
            attachments = self.broadcastbot.message_handler.empty_list_to_none(ctx.message.base64_attachments)

            await self.broadcastbot.send(user_id, message, base64_attachments=attachments)
            await self.broadcastbot.reply_with_warn_on_failure(ctx, "Message sent")
            self.broadcastbot.logger.info(
                "Sent message from admin %s to user %s",
                self.broadcastbot.admin.admin_id,
                user_id,
            )
        except Exception:
            self.broadcastbot.logger.exception("")
            try:
                await self.broadcastbot.reply_with_warn_on_failure(ctx, "Failed to send the message to the user!")
            except Exception:
                self.broadcastbot.logger.exception("")

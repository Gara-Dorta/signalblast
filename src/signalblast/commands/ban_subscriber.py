from __future__ import annotations

from typing import TYPE_CHECKING

from signalbot import DataMessageContext, DataMessageHandler, ReceiptType, SendMessage, regex_triggered

from signalblast.commands_strings import AdminCommandArgs, AdminCommandStrings, CommandRegex

if TYPE_CHECKING:
    from signalblast.broadcastbot import BroadcasBot


class BanSubscriber(DataMessageHandler):
    def __init__(self, bot: BroadcasBot) -> None:
        super().__init__()
        self.broadcastbot = bot

    @regex_triggered(CommandRegex.ban_subscriber)
    async def handle_data_message(self, context: DataMessageContext) -> None:
        try:
            await context.send_receipt(ReceiptType.READ)

            user_id = self.broadcastbot.message_handler.remove_command_from_message(
                context.message.text,
                AdminCommandStrings.ban_subscriber,
            )

            if not await self.broadcastbot.is_user_admin(context, AdminCommandStrings.ban_subscriber):
                return

            if user_id is None:
                usage = (
                    f"Missing argument, usage: {AdminCommandStrings.ban_subscriber} {AdminCommandArgs.ban_subscriber}"
                )
                await self.broadcastbot.reply_with_warn_on_failure(context, usage)
                return

            if user_id in self.broadcastbot.subscribers:
                await self.broadcastbot.subscribers.remove(user_id)

            await self.broadcastbot.banned_users.add(user_id)

            await context.bot.messages.send(SendMessage(text="You have been banned"), user_id)
            await self.broadcastbot.reply_with_warn_on_failure(context, "Successfully banned user")

            self.broadcastbot.logger.info("Banned user %s", user_id)
        except Exception:
            self.broadcastbot.logger.exception("")
            try:
                await self.broadcastbot.reply_with_warn_on_failure(context, "Failed to ban user")
            except Exception:
                self.broadcastbot.logger.exception("")

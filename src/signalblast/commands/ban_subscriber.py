from signalbot import Command, regex_triggered
from signalbot import Context as ChatContext

from signalblast.broadcastbot import BroadcasBot
from signalblast.commands_strings import AdminCommandStrings, CommandRegex


class BanSubscriber(Command):
    def __init__(self, bot: BroadcasBot) -> None:
        super().__init__()
        self.broadcastbot = bot

    @regex_triggered(CommandRegex.ban_subscriber)
    async def handle(self, ctx: ChatContext) -> None:
        try:
            await ctx.receipt(receipt_type="read")

            user_id = self.broadcastbot.message_handler.remove_command_from_message(
                ctx.message.text,
                AdminCommandStrings.ban_subscriber,
            )

            if not await self.broadcastbot.is_user_admin(ctx, AdminCommandStrings.ban_subscriber):
                return

            if user_id in self.broadcastbot.subscribers:
                await self.broadcastbot.subscribers.remove(user_id)

            user_phone_number = self.broadcastbot.subscribers.get_phone_number(user_id)
            await self.broadcastbot.banned_users.add(user_id, user_phone_number)

            await self.broadcastbot.send(user_id, "You have been banned")
            await self.broadcastbot.reply_with_warn_on_failure(ctx, "Successfully banned user")

            self.broadcastbot.logger.info("Banned user %s", user_id)
        except Exception:
            self.broadcastbot.logger.exception("")
            try:
                await self.broadcastbot.reply_with_warn_on_failure(ctx, "Failed to ban user")
            except Exception:
                self.broadcastbot.logger.exception("")

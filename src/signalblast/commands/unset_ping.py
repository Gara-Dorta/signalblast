from signalbot import Command, regex_triggered
from signalbot import Context as ChatContext

from signalblast.broadcastbot import BroadcasBot
from signalblast.commands_strings import AdminCommandStrings, CommandRegex


class UnsetPing(Command):
    def __init__(self, bot: BroadcasBot) -> None:
        super().__init__()
        self.broadcastbot = bot

    @regex_triggered(CommandRegex.unset_ping)
    async def handle(self, ctx: ChatContext) -> None:
        try:
            await ctx.receipt(receipt_type="read")

            if not await self.broadcastbot.is_user_admin(ctx, AdminCommandStrings.unset_ping):
                return

            if self.broadcastbot.ping_job is None:
                await ctx.reply("Cannot unset because ping was not set!")
                return

            self.broadcastbot.scheduler.remove_job(self.broadcastbot.ping_job.id)
            self.broadcastbot.ping_job = None
            await ctx.reply("Ping unset!")
        except Exception:
            self.broadcastbot.logger.exception("")
            try:
                await self.broadcastbot.reply_with_warn_on_failure(ctx, "Failed to unset ping")
            except Exception:
                self.broadcastbot.logger.exception("")

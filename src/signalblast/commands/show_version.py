from signalbot import Command, regex_triggered
from signalbot import Context as ChatContext
from signalbot import __version__ as __signalbot_version__

from signalblast import __version__ as __signalblast_version__
from signalblast.broadcastbot import BroadcasBot
from signalblast.commands_strings import AdminCommandStrings, CommandRegex


class ShowVersion(Command):
    def __init__(self, bot: BroadcasBot) -> None:
        super().__init__()
        self.broadcastbot = bot

    @regex_triggered(CommandRegex.show_version)
    async def handle(self, ctx: ChatContext) -> None:
        try:
            await ctx.receipt(receipt_type="read")

            if not await self.broadcastbot.is_user_admin(ctx, AdminCommandStrings.show_version):
                return

            signal_cli_rest_api_version = await ctx.bot.signal_cli_rest_api_version()

            version_msg = "Versions:\n"
            version_msg += f"\tsignalblast: {__signalblast_version__}\n"
            version_msg += f"\tsignalBot: {__signalbot_version__}\n"
            version_msg += f"\tsignal-cli-rest-api: {signal_cli_rest_api_version}\n"

            await self.broadcastbot.reply_with_warn_on_failure(ctx, version_msg)

            self.broadcastbot.logger.info("Shown version to user %s", ctx.message.source_uuid)
        except Exception:
            self.broadcastbot.logger.exception("")
            try:
                await self.broadcastbot.reply_with_warn_on_failure(ctx, "Failed to show version")
            except Exception:
                self.broadcastbot.logger.exception("")

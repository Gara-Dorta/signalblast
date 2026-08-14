from __future__ import annotations

from typing import TYPE_CHECKING

from signalbot import DataMessageContext, DataMessageHandler, ReceiptType, regex_triggered
from signalbot import __version__ as __signalbot_version__

from signalblast import __version__ as __signalblast_version__
from signalblast.commands_strings import AdminCommandStrings, CommandRegex

if TYPE_CHECKING:
    from signalblast.broadcastbot import BroadcasBot


class ShowVersion(DataMessageHandler):
    def __init__(self, bot: BroadcasBot) -> None:
        super().__init__()
        self.broadcastbot = bot

    @regex_triggered(CommandRegex.show_version)
    async def handle_data_message(self, context: DataMessageContext) -> None:
        try:
            await context.send_receipt(ReceiptType.READ)

            if not await self.broadcastbot.is_user_admin(context, AdminCommandStrings.show_version):
                return

            signal_cli_rest_api_version = (await context.bot.general.about()).version

            version_msg = "Versions:\n"
            version_msg += f"\tsignalblast: {__signalblast_version__}\n"
            version_msg += f"\tsignalBot: {__signalbot_version__}\n"
            version_msg += f"\tsignal-cli-rest-api: {signal_cli_rest_api_version}\n"

            await self.broadcastbot.reply_with_warn_on_failure(context, version_msg)

            self.broadcastbot.logger.info("Shown version to user %s", context.message.source_uuid)
        except Exception:
            self.broadcastbot.logger.exception("")
            try:
                await self.broadcastbot.reply_with_warn_on_failure(context, "Failed to show version")
            except Exception:
                self.broadcastbot.logger.exception("")

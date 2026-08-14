from __future__ import annotations

from typing import TYPE_CHECKING

from signalbot import DataMessageContext, DataMessageHandler, ReceiptType, regex_triggered

from signalblast.commands_strings import CommandRegex, PublicCommandStrings

if TYPE_CHECKING:
    from signalblast.broadcastbot import BroadcasBot


class DisplayHelp(DataMessageHandler):
    def __init__(self, bot: BroadcasBot) -> None:
        super().__init__()
        self.broadcastbot = bot

    def _get_help_message(self, input_message: str, subscriber_uuid: str) -> str:
        is_wrong_command = not input_message.startswith(PublicCommandStrings.help)

        if subscriber_uuid != self.broadcastbot.admin.admin_id:
            if is_wrong_command:
                return self.broadcastbot.wrong_command_message
            return self.broadcastbot.help_message
        if is_wrong_command:
            return self.broadcastbot.admin_wrong_command_message
        return self.broadcastbot.admin_help_message

    @regex_triggered(CommandRegex.help)
    async def handle_data_message(self, context: DataMessageContext) -> None:
        try:
            await context.send_receipt(ReceiptType.READ)

            subscriber_uuid = context.message.source_uuid
            message = context.message.text
            if subscriber_uuid is None or message is None:
                self.broadcastbot.logger.warning("Received a help message with no source_uuid or text")
                return

            help_message = self._get_help_message(message, subscriber_uuid)

            await self.broadcastbot.reply_with_warn_on_failure(context, help_message)
            self.broadcastbot.logger.info("Sent help message to %s", subscriber_uuid)
        except Exception:
            self.broadcastbot.logger.exception("")

from signalbot import Command, regex_triggered
from signalbot import Context as ChatContext

from signalblast.broadcastbot import BroadcasBot
from signalblast.commands_strings import CommandRegex, PublicCommandStrings


class DisplayHelp(Command):
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
    async def handle(self, ctx: ChatContext) -> None:
        try:
            await ctx.receipt(receipt_type="read")

            subscriber_uuid = ctx.message.source_uuid
            message = ctx.message.text

            help_message = self._get_help_message(message, subscriber_uuid)

            await self.broadcastbot.reply_with_warn_on_failure(ctx, help_message)
            self.broadcastbot.logger.info("Sent help message to %s", subscriber_uuid)
        except Exception:
            self.broadcastbot.logger.exception("")

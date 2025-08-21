from signalbot import Command, regex_triggered
from signalbot import Context as ChatContext

from signalblast.broadcastbot import BroadcasBot
from signalblast.commands_strings import AdminCommandStrings, CommandRegex


class LastMsgUserUuid(Command):
    def __init__(self, bot: BroadcasBot) -> None:
        super().__init__()
        self.broadcastbot = bot

    @regex_triggered(CommandRegex.last_msg_user_uuid)
    async def handle(self, ctx: ChatContext) -> None:
        try:
            await ctx.receipt(receipt_type="read")
            if not await self.broadcastbot.is_user_admin(ctx, AdminCommandStrings.last_msg_user_uuid):
                return
            msg = f"Last message was sent by\n\t{self.broadcastbot.last_msg_user_uuid}"
            await self.broadcastbot.send(self.broadcastbot.admin.admin_id, msg)

            self.broadcastbot.logger.info(msg)
        except Exception:
            self.broadcastbot.logger.exception("")
            try:
                await self.broadcastbot.reply_with_warn_on_failure(ctx, "Failed get UUID")
            except Exception:
                self.broadcastbot.logger.exception("")

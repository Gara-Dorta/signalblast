from signalbot import Command, regex_triggered
from signalbot import Context as ChatContext

from signalblast.broadcastbot import BroadcasBot
from signalblast.commands_strings import CommandRegex


class Unsubscribe(Command):
    def __init__(self, bot: BroadcasBot) -> None:
        super().__init__()
        self.broadcastbot = bot

    @regex_triggered(CommandRegex.unsubscribe)
    async def handle(self, ctx: ChatContext) -> None:
        try:
            await ctx.receipt(receipt_type="read")

            subscriber_uuid = ctx.message.source_uuid

            if subscriber_uuid not in self.broadcastbot.subscribers:
                await self.broadcastbot.reply_with_warn_on_failure(ctx, "Not subscribed!")
                self.broadcastbot.logger.info("%s tried to unsubscribe but they are not subscribed", subscriber_uuid)
                return

            await self.broadcastbot.subscribers.remove(subscriber_uuid)
            await self.broadcastbot.reply_with_warn_on_failure(ctx, "Successfully unsubscribed!")
            self.broadcastbot.logger.info("%s unsubscribed", subscriber_uuid)
        except Exception:
            self.broadcastbot.logger.exception("")
            try:
                await self.broadcastbot.reply_with_warn_on_failure(ctx, "Could not unsubscribe!")
            except Exception:
                self.broadcastbot.logger.exception("")

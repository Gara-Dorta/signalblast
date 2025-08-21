from signalbot import Command, regex_triggered
from signalbot import Context as ChatContext

from signalblast.broadcastbot import BroadcasBot
from signalblast.commands_strings import CommandRegex


class Subscribe(Command):
    def __init__(self, bot: BroadcasBot) -> None:
        super().__init__()
        self.broadcastbot = bot

    async def subscribe(self, ctx: ChatContext, *, verbose: bool = False) -> None:
        try:
            await ctx.receipt(receipt_type="read")

            subscriber_uuid = ctx.message.source_uuid
            if subscriber_uuid in self.broadcastbot.subscribers:
                if verbose:
                    await self.broadcastbot.reply_with_warn_on_failure(ctx, "Already subscribed!")
                    self.broadcastbot.logger.info("Already subscribed!")
                return

            if subscriber_uuid in self.broadcastbot.banned_users:
                if verbose:
                    await self.broadcastbot.reply_with_warn_on_failure(ctx, "This number is not allowed to subscribe")
                    self.broadcastbot.logger.info("%s was not allowed to subscribe", subscriber_uuid)
                return

            await self.broadcastbot.subscribers.add(subscriber_uuid, ctx.message.source_number)

            if self.broadcastbot.expiration_time is not None:
                await self.broadcastbot.set_expiration_time(subscriber_uuid, self.broadcastbot.expiration_time)

            await self.broadcastbot.reply_with_warn_on_failure(ctx, self.broadcastbot.welcome_message)

            self.broadcastbot.logger.info("%s subscribed", subscriber_uuid)
        except Exception:
            self.broadcastbot.logger.exception("")
            try:
                await self.broadcastbot.reply_with_warn_on_failure(ctx, "Could not subscribe!")
            except Exception:
                self.broadcastbot.logger.exception("")

    @regex_triggered(CommandRegex.subscribe)
    async def handle(self, ctx: ChatContext) -> None:
        await Subscribe.subscribe(self, ctx, verbose=True)

from signalbot import Command, regex_triggered
from signalbot import Context as ChatContext

from signalblast.broadcastbot import BroadcasBot
from signalblast.commands_strings import AdminCommandStrings, CommandRegex


class SetPing(Command):
    def __init__(self, bot: BroadcasBot) -> None:
        super().__init__()
        self.broadcastbot = bot

    async def _send_ping(self, receiver: str) -> None:
        try:
            await self.broadcastbot.send(receiver, "Ping")
        except Exception:
            self.broadcastbot.logger.exception("")
            try:
                await self.broadcastbot.send(receiver, "Failed to send ping")
            except Exception:
                self.broadcastbot.logger.exception("")

    async def process_ping_msg(self, ctx: ChatContext) -> None:
        ping_time = self.broadcastbot.message_handler.remove_command_from_message(
            ctx.message.text,
            AdminCommandStrings.set_ping,
        )

        if not await self.broadcastbot.is_user_admin(ctx, AdminCommandStrings.set_ping):
            return

        if ctx.message.group is None:
            error_msg = "Empty group for set ping message"
            raise RuntimeError(error_msg)

        if self.broadcastbot.expiration_time is not None:
            await self.broadcastbot.set_group_expiration_time(ctx.message.group, self.broadcastbot.expiration_time)

        if self.broadcastbot.ping_job is not None:
            self.broadcastbot.scheduler.remove_job(self.broadcastbot.ping_job.id)
            self.broadcastbot.logger.info("Unset old ping job")
            await self.broadcastbot.reply_with_warn_on_failure(ctx, "Unset old ping job")

        self.broadcastbot.ping_job = self.broadcastbot.scheduler.add_job(
            self._send_ping,
            "interval",
            seconds=int(ping_time),
            args=[ctx.message.group],
        )

        await self.broadcastbot.reply_with_warn_on_failure(ctx, f"Ping set every {ping_time} seconds")
        self.broadcastbot.logger.info("Ping set every %s seconds", ping_time)

    @regex_triggered(CommandRegex.set_ping)
    async def handle(self, ctx: ChatContext) -> None:
        try:
            await ctx.receipt(receipt_type="read")

            await self.process_ping_msg(ctx)
        except Exception:
            self.broadcastbot.logger.exception("")
            try:
                await self.broadcastbot.reply_with_warn_on_failure(ctx, "Failed set ping")
            except Exception:
                self.broadcastbot.logger.exception("")

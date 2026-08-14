from __future__ import annotations

from typing import TYPE_CHECKING

from signalbot import DataMessageContext, DataMessageHandler, ReceiptType, regex_triggered

from signalblast.commands_strings import AdminCommandArgs, AdminCommandStrings, CommandRegex

if TYPE_CHECKING:
    from signalblast.broadcastbot import BroadcasBot


class SetPing(DataMessageHandler):
    def __init__(self, bot: BroadcasBot) -> None:
        super().__init__()
        self.broadcastbot = bot

    async def process_ping_msg(self, ctx: DataMessageContext) -> None:
        ping_time = self.broadcastbot.message_handler.remove_command_from_message(
            ctx.message.text,
            AdminCommandStrings.set_ping,
        )

        if not await self.broadcastbot.is_user_admin(ctx, AdminCommandStrings.set_ping):
            return

        if ping_time is None:
            usage = f"Missing argument, usage: {AdminCommandStrings.set_ping} {AdminCommandArgs.set_ping}"
            await self.broadcastbot.reply_with_warn_on_failure(ctx, usage)
            return

        if ctx.message.group_info is None or ctx.message.group_info.group_id is None:
            error_msg = "Empty group for set ping message"
            raise RuntimeError(error_msg)

        group_id = ctx.message.group_info.group_id

        if self.broadcastbot.expiration_time is not None:
            await self.broadcastbot.set_group_expiration_time(group_id, self.broadcastbot.expiration_time)

        if self.broadcastbot.ping_job is not None:
            self.broadcastbot.scheduler.remove_job(self.broadcastbot.ping_job.id)
            self.broadcastbot.logger.info("Unset old ping job")
            await self.broadcastbot.reply_with_warn_on_failure(ctx, "Unset old ping job")

        self.broadcastbot.schedule_ping(group_id, int(ping_time))

        await self.broadcastbot.reply_with_warn_on_failure(ctx, f"Ping set every {ping_time} seconds")
        self.broadcastbot.logger.info("Ping set every %s seconds", ping_time)

    @regex_triggered(CommandRegex.set_ping)
    async def handle_data_message(self, context: DataMessageContext) -> None:
        try:
            await context.send_receipt(ReceiptType.READ)

            await self.process_ping_msg(context)
        except Exception:
            self.broadcastbot.logger.exception("")
            try:
                await self.broadcastbot.reply_with_warn_on_failure(context, "Failed set ping")
            except Exception:
                self.broadcastbot.logger.exception("")

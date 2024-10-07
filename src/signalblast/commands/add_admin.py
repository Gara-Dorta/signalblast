import asyncio
import functools
from re import Pattern
from typing import Optional

from signalbot import Command
from signalbot import Context as ChatContext

from signalblast.broadcastbot import BroadcasBot
from signalblast.commands_strings import AdminCommandStrings, CommandRegex, PublicCommandStrings
from signalblast.utils import triggered


class AddAdmin(Command):
    def __init__(self, bot: BroadcasBot) -> None:
        super().__init__()
        self.broadcastbot = bot

    @triggered(CommandRegex.add_admin)
    async def handle(self, ctx: ChatContext) -> None:
        try:
            subscriber_uuid = ctx.message.source_uuid
            password = self.broadcastbot.message_handler.remove_command_from_message(
                ctx.message.text, AdminCommandStrings.add_admin
            )

            previous_admin = self.broadcastbot.admin.admin_id
            if await self.broadcastbot.admin.add(subscriber_uuid, password):
                await self.broadcastbot.reply_with_warn_on_failure(ctx, "You have been added as admin!")
                if previous_admin is not None and subscriber_uuid != previous_admin:
                    msg_to_admin = self.broadcastbot.message_handler.compose_message_to_admin(
                        "You are no longer an admin!", subscriber_uuid
                    )
                    await self.broadcastbot.send(previous_admin, msg_to_admin)
                log_message = f"Previous admin was {previous_admin}, new admin is {subscriber_uuid}"
                self.broadcastbot.logger.info(log_message)
            else:
                await self.broadcastbot.reply_with_warn_on_failure(ctx, "Adding failed, admin password is incorrect!")
                if previous_admin is not None:
                    msg_to_admin = self.broadcastbot.message_handler.compose_message_to_admin(
                        "Tried to be added as admin", subscriber_uuid
                    )
                    await self.broadcastbot.send(previous_admin, msg_to_admin)
                self.broadcastbot.logger.warning(f"{subscriber_uuid} failed password check for add_admin")
        except Exception as e:
            self.broadcastbot.logger.error(e, exc_info=True)

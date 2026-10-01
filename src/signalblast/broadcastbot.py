from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from signalbot import Context, DataMessageContext, SendMessage, SignalBot, SignalBotError, UpdateContact

from signalblast.admin import Admin
from signalblast.message_handler import MessageHandler
from signalblast.storage import SignalblastStorage, UserTable
from signalblast.utils import route_signalbot_logs_to_root

if TYPE_CHECKING:
    from signalblast.settings import Settings


class BroadcastBot:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.logger = logging.getLogger("signalblast")

        settings.data_dir.mkdir(parents=True, exist_ok=True)
        # signalblast keeps its own database, signalbot's key/value storage is unused
        self.signal_bot = SignalBot(
            {
                "signal_service": settings.signal_service,
                "phone_number": settings.phone_number,
                "storage": {"type": "in-memory"},
            },
        )
        route_signalbot_logs_to_root()
        self.scheduler = self.signal_bot.scheduler

        self.db = SignalblastStorage(settings.db_path)
        self.subscribers = UserTable(self.db, "subscribers")
        self.banned_users = UserTable(self.db, "banned_users")

        password = settings.password.get_secret_value() if settings.password is not None else None
        self.admin = Admin.load(self.db, password)

        self.message_handler = MessageHandler()
        self.help_message = self.message_handler.compose_help_message(instructions_url=settings.instructions_url)
        self.wrong_command_message = self.message_handler.compose_help_message(
            is_help=False,
            instructions_url=settings.instructions_url,
        )
        self.admin_help_message = self.message_handler.compose_help_message(
            add_admin_commands=True,
            instructions_url=settings.instructions_url,
        )
        self.admin_wrong_command_message = self.message_handler.compose_help_message(
            add_admin_commands=True,
            is_help=False,
            instructions_url=settings.instructions_url,
        )
        self.welcome_message = settings.welcome_message
        self.must_subscribe_message = self.message_handler.compose_must_subscribe_message(
            instructions_url=settings.instructions_url,
        )
        # 0 disables disappearing messages
        self.expiration_time: int | None = settings.expiration_time or None

    def start(self) -> None:
        self.signal_bot.start()

    @property
    def last_msg_user_uuid(self) -> str | None:
        return self.db.get_last_broadcast_uuid()

    @last_msg_user_uuid.setter
    def last_msg_user_uuid(self, subscriber_uuid: str) -> None:
        self.db.set_last_broadcast_uuid(subscriber_uuid)

    async def reply_with_warn_on_failure(self, ctx: DataMessageContext, message: str) -> bool:
        try:
            await ctx.reply(SendMessage(text=message))
        except SignalBotError:
            self.logger.warning("Could not send message to %s", ctx.message.source_uuid)
            return False
        else:
            return True

    async def send_with_warn_on_failure(self, ctx: Context, message: str) -> bool:
        try:
            await ctx.send(SendMessage(text=message))
        except SignalBotError:
            self.logger.warning("Could not send message to %s", ctx.message.source_uuid)
            return False
        else:
            return True

    async def is_user_admin(self, ctx: DataMessageContext, command: str) -> bool:
        subscriber_uuid = ctx.message.source_uuid
        if self.admin.admin_id is None:
            await self.reply_with_warn_on_failure(ctx, "I'm sorry but there are no admins")
            self.logger.info("Tried to %s but there are no admins! %s", command, subscriber_uuid)
            return False

        if self.admin.admin_id != subscriber_uuid:
            await self.reply_with_warn_on_failure(ctx, "I'm sorry but you are not an admin")
            msg_to_admin = self.message_handler.compose_message_to_admin(f"Tried to {command}", subscriber_uuid)
            await ctx.bot.messages.send(SendMessage(text=msg_to_admin), self.admin.admin_id)
            self.logger.info("%s tried to %s but admin is %s", subscriber_uuid, command, self.admin.admin_id)
            return False

        return True

    async def set_expiration_time(self, receiver: str, expiration_in_seconds: int) -> None:
        await self.signal_bot.contacts.update(UpdateContact(expiration_in_seconds=expiration_in_seconds), receiver)

    async def delete_old_timestamps(self) -> None:
        """Signal only allows editing messages within 24 hours.
        No point in keeping the information for older messages"""
        cutoff = int((datetime.now(tz=UTC) - timedelta(days=1)).timestamp() * 1000)
        num_deleted = self.db.delete_broadcast_timestamps_before(cutoff)
        self.logger.info("Deleted %s expired broadcast timestamps", num_deleted)

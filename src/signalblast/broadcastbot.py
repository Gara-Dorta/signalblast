from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from signalbot import Context, DataMessageContext, SendMessage, SignalBot, SignalBotError, UpdateContact

from signalblast.admin import Admin
from signalblast.message_handler import MessageHandler
from signalblast.storage import SignalblastStorage, UserTable
from signalblast.utils import get_data_path

if TYPE_CHECKING:
    from asyncio import Task
    from logging import Logger


class BroadcasBot:
    def __init__(self, config: dict) -> None:
        self.signal_bot = SignalBot(config)
        self.db = SignalblastStorage(get_data_path() / "signalblast.db", check_same_thread=False)
        self.signal_bot.storage = self.db

        self.health_check_task: Task | None = None
        self.log_rollover_task: Task | None = None

        # Type hint the other attributes that will get defined in load_data
        self.subscribers: UserTable
        self.banned_users: UserTable
        self.admin: Admin
        self.message_handler: MessageHandler
        self.help_message: str
        self.wrong_command_message: str
        self.admin_help_message: str
        self.admin_wrong_command_message: str
        self.must_subscribe_message: str
        self.logger: Logger
        self.expiration_time: int | None
        self.welcome_message: str

        self.scheduler = self.signal_bot.scheduler

    def start(self) -> None:
        self.signal_bot.start()

    async def load_data(
        self,
        logger: Logger,
        admin_pass: str | None,
        expiration_time: int | None,
        welcome_message: str | None = None,
        instructions_url: str | None = None,
    ) -> None:
        self.subscribers = UserTable(self.db, "subscribers")
        self.banned_users = UserTable(self.db, "banned_users")

        self.admin = await Admin.load(self.db, admin_pass)
        self.message_handler = MessageHandler()

        self.help_message = self.message_handler.compose_help_message(instructions_url=instructions_url)
        self.wrong_command_message = self.message_handler.compose_help_message(
            is_help=False,
            instructions_url=instructions_url,
        )
        self.admin_help_message = self.message_handler.compose_help_message(
            add_admin_commands=True,
            instructions_url=instructions_url,
        )
        self.admin_wrong_command_message = self.message_handler.compose_help_message(
            add_admin_commands=True,
            is_help=False,
            instructions_url=instructions_url,
        )
        self.welcome_message = self.message_handler.compose_welcome_message(welcome_message)

        self.must_subscribe_message = self.message_handler.compose_must_subscribe_message(
            instructions_url=instructions_url,
        )

        self.expiration_time = expiration_time

        self.logger = logger
        self.logger.debug("BotAnswers is initialised")

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

    async def set_expiration_time(self, reciver: str, expiration_in_seconds: int) -> None:
        await self.signal_bot.contacts.update(UpdateContact(expiration_in_seconds=expiration_in_seconds), reciver)

    async def delete_old_timestamps(self) -> None:
        """Signal only allows editing messges within 24 hours.
        No point in keeping the information for older messages"""
        cutoff = int((datetime.now(tz=UTC) - timedelta(days=1)).timestamp() * 1000)
        num_deleted = self.db.delete_broadcast_timestamps_before(cutoff)
        self.logger.info("Deleted %s expired broadcast timestamps", num_deleted)

from datetime import datetime, timedelta, timezone
from logging import Logger
from threading import Lock
from typing import TYPE_CHECKING

from signalbot import Context as ChatContext
from signalbot import SignalBot

from signalblast.admin import Admin
from signalblast.message_handler import MessageHandler
from signalblast.users import Users
from signalblast.utils import TimestampData, get_data_path

if TYPE_CHECKING:
    from asyncio import Task

    from apscheduler.job import Job


class BroadcasBot:
    subscribers_data_path = get_data_path() / "subscribers.csv"
    banned_users_data_path = get_data_path() / "banned_users.csv"

    def __init__(self, config: dict) -> None:
        self.signal_bot = SignalBot(config)
        self.ping_job: Job | None = None
        self.last_msg_user_uuid: str | None = None
        self.health_check_task: Task | None = None
        self.log_rollover_task: Task | None = None

        # Type hint the other attributes that will get defined in load_data
        self.subscribers: Users
        self.banned_users: Users
        self.admin: Admin
        self.message_handler: MessageHandler
        self.help_message: str
        self.wrong_command_message: str
        self.admin_help_message: str
        self.admin_wrong_command_message: str
        self.must_subscribe_message: str
        self.logger: Logger
        self.expiration_time: int
        self.welcome_message: str
        self.storage_lock: Lock

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
        self.subscribers = await Users.load_from_file(self.subscribers_data_path)
        self.banned_users = await Users.load_from_file(self.banned_users_data_path)

        self.admin = await Admin.load_from_file(admin_pass)
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

        self.storage_lock = Lock()

        self.logger = logger
        self.logger.debug("BotAnswers is initialised")

    async def reply_with_warn_on_failure(self, ctx: ChatContext, message: str) -> bool:
        if await ctx.reply(message):
            return True
        self.logger.warning("Could not send message to %s", ctx.message.source_uuid)
        return False

    async def is_user_admin(self, ctx: ChatContext, command: str) -> bool:
        subscriber_uuid = ctx.message.source_uuid
        if self.admin.admin_id is None:
            await self.reply_with_warn_on_failure(ctx, "I'm sorry but there are no admins")
            self.logger.info("Tried to %s but there are no admins! %s", command, subscriber_uuid)
            return False

        if self.admin.admin_id != subscriber_uuid:
            await self.reply_with_warn_on_failure(ctx, "I'm sorry but you are not an admin")
            msg_to_admin = self.message_handler.compose_message_to_admin(f"Tried to {command}", subscriber_uuid)
            await ctx.bot.send(self.admin.admin_id, msg_to_admin)
            self.logger.info("%s tried to %s but admin is %s", subscriber_uuid, command, self.admin.admin_id)
            return False

        return True

    async def set_expiration_time(self, reciver: str, expiration_in_seconds: int) -> None:
        await self.signal_bot.update_contact(reciver, expiration_in_seconds=expiration_in_seconds)

    async def set_group_expiration_time(self, group_id: str, expiration_in_seconds: int) -> None:
        await self.signal_bot.update_group(group_id, expiration_in_seconds=expiration_in_seconds)

    async def delete_old_timestamps(self) -> None:
        """Signal only allows editing messges within 24 hours.
        No point in keeping the information for older messages"""
        cursor = self.signal_bot.storage._sqlite.execute("SELECT key FROM signalbot")  # noqa: SLF001
        keys = [row[0] for row in cursor.fetchall()]
        for key in keys:
            value = TimestampData.model_validate(self.signal_bot.storage.read(key))
            if datetime.fromtimestamp(value.timestamp / 1000, tz=timezone.utc) < (
                datetime.now(tz=timezone.utc) - timedelta(days=1)
            ):
                self.storage_lock.acquire()
                self.signal_bot.storage.delete(key)
                self.storage_lock.release()
                self.logger.info("Deleted expired key with timestamp: %s", value.timestamp)

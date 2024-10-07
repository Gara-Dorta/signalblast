from collections.abc import Callable
from logging import Logger
from pathlib import Path
from typing import TYPE_CHECKING

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from signalbot import Command, Message, SignalBot
from signalbot import Context as ChatContext

from signalblast.admin import Admin
from signalblast.message_handler import MessageHandler
from signalblast.users import Users
from signalblast.utils import get_code_data_path

if TYPE_CHECKING:
    from apscheduler.job import Job


class BroadcasBot:
    subscribers_data_path = get_code_data_path() / "subscribers.csv"
    banned_users_data_path = get_code_data_path() / "banned_users.csv"

    def __init__(self, config: dict) -> None:
        self._bot = SignalBot(config)
        self.ping_job: Job | None = None

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

    async def send(  # noqa: PLR0913 Too many arguments in function definition
        self,
        receiver: str,
        text: str,
        base64_attachments: list | None = None,
        quote_author: str | None = None,
        quote_mentions: list | None = None,
        quote_message: str | None = None,
        quote_timestamp: str | None = None,
        mentions: list | None = None,
        text_mode: str | None = None,
        listen: bool = False,  # noqa: FBT001, FBT002
    ) -> str:
        return await self._bot.send(
            receiver=receiver,
            text=text,
            base64_attachments=base64_attachments,
            quote_author=quote_author,
            quote_mentions=quote_mentions,
            quote_message=quote_message,
            quote_timestamp=quote_timestamp,
            mentions=mentions,
            text_mode=text_mode,
            listen=listen,
        )

    def register(
        self,
        command: Command,
        contacts: list[str] | bool | None = True,  # noqa: FBT002
        groups: list[str] | bool | None = False,  # noqa: FBT002
        f: Callable[[Message], bool] | None = None,
    ) -> None:
        self._bot.register(command=command, contacts=contacts, groups=groups, f=f)

    def start(self) -> None:
        self._bot.start()

    @property
    def scheduler(self) -> AsyncIOScheduler:
        return self._bot.scheduler

    async def load_data(
        self,
        logger: Logger,
        admin_pass: str | None,
        expiration_time: int | None,
        signal_data_path: Path,
        welcome_message: str | None = None,
    ) -> None:
        self.subscribers = await Users.load_from_file(self.subscribers_data_path)
        self.banned_users = await Users.load_from_file(self.banned_users_data_path)

        self.admin = await Admin.load_from_file(admin_pass)
        self.message_handler = MessageHandler(signal_data_path / "attachments")

        self.help_message = self.message_handler.compose_help_message(is_help=True)
        self.wrong_command_message = self.message_handler.compose_help_message(is_help=False)
        self.admin_help_message = self.message_handler.compose_help_message(add_admin_commands=True)
        self.admin_wrong_command_message = self.message_handler.compose_help_message(
            add_admin_commands=True,
            is_help=False,
        )
        self.welcome_message = self.message_handler.compose_welcome_message(welcome_message)

        self.must_subscribe_message = self.message_handler.compose_must_subscribe_message()

        self.expiration_time = expiration_time

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
            await self.send(self.admin.admin_id, msg_to_admin)
            self.logger.info("%s tried to %s but admin is %s", subscriber_uuid, command, self.admin.admin_id)
            return False

        return True

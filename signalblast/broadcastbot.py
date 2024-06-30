from logging import Logger
from pathlib import Path
from typing import Callable, List, Optional, Union

from apscheduler.job import Job
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from signalbot import Command
from signalbot import Context as ChatContext
from signalbot import Message, SignalBot

from signalblast.admin import Admin
from signalblast.message_handler import MessageHandler
from signalblast.users import Users
from signalblast.utils import get_code_data_path


class BroadcasBot:
    subscribers_data_path = get_code_data_path() / "subscribers.csv"
    banned_users_data_path = get_code_data_path() / "banned_users.csv"

    def __init__(self, config: dict):
        self._bot = SignalBot(config)
        self.ping_job: Optional[Job] = None

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

    async def send(
        self,
        receiver: str,
        text: str,
        base64_attachments: list = None,
        quote_author: str = None,
        quote_mentions: list = None,
        quote_message: str = None,
        quote_timestamp: str = None,
        mentions: list = None,
        text_mode: str = None,
        listen: bool = False,
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
        contacts: Optional[Union[List[str], bool]] = True,
        groups: Optional[Union[List[str], bool]] = False,
        f: Optional[Callable[[Message], bool]] = None,
    ):
        self._bot.register(command=command, contacts=contacts, groups=groups, f=f)

    def start(self):
        self._bot.start()

    @property
    def scheduler(self) -> AsyncIOScheduler:
        return self._bot.scheduler

    async def load_data(
        self,
        logger: Logger,
        admin_pass: Optional[str],
        expiration_time: Optional[int],
        signal_data_path: Path,
        welcome_message: Optional[str] = None,
    ):
        self.subscribers = await Users.load_from_file(self.subscribers_data_path)
        self.banned_users = await Users.load_from_file(self.banned_users_data_path)

        self.admin = await Admin.load_from_file(admin_pass)
        self.message_handler = MessageHandler(signal_data_path / "attachments")

        self.help_message = self.message_handler.compose_help_message(is_help=True)
        self.wrong_command_message = self.message_handler.compose_help_message(is_help=False)
        self.admin_help_message = self.message_handler.compose_help_message(add_admin_commands=True)
        self.admin_wrong_command_message = self.message_handler.compose_help_message(
            add_admin_commands=True, is_help=False
        )
        self.welcome_message = self.message_handler.compose_welcome_message(welcome_message)

        self.must_subscribe_message = self.message_handler.compose_must_subscribe_message()

        self.expiration_time = expiration_time

        self.logger = logger
        self.logger.debug("BotAnswers is initialised")

    async def reply_with_warn_on_failure(self, ctx: ChatContext, message: str) -> bool:
        if await ctx.reply(message):
            return True
        else:
            self.logger.warning(f"Could not send message to {ctx.message.source_uuid}")
            return False

    async def is_user_admin(self, ctx: ChatContext, command: str) -> bool:
        subscriber_uuid = ctx.message.source_uuid
        if self.admin.admin_id is None:
            await self.reply_with_warn_on_failure(ctx, "I'm sorry but there are no admins")
            self.logger.info(f"Tried to {command} but there are no admins! {subscriber_uuid}")
            return False

        if self.admin.admin_id != subscriber_uuid:
            await self.reply_with_warn_on_failure(ctx, "I'm sorry but you are not an admin")
            msg_to_admin = self.message_handler.compose_message_to_admin(f"Tried to {command}", subscriber_uuid)
            await self.send(self.admin.admin_id, msg_to_admin)
            self.logger.info(f"{subscriber_uuid} tried to {command} but admin is {self.admin.admin_id}")
            return False

        return True

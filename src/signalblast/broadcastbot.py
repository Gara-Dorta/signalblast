from __future__ import annotations

import logging
from datetime import timedelta
from typing import TYPE_CHECKING

from signalbot import SendMessage, SignalBot, SignalBotError, UpdateContact

from signalblast.database import Database
from signalblast.passwords import hash_password
from signalblast.utils import now_ms, route_signalbot_logs_to_root

if TYPE_CHECKING:
    from signalbot import DataMessageContext, SentMessage

    from signalblast.commands.broadcast import BroadcastRetry
    from signalblast.settings import Settings

logger = logging.getLogger(__name__)

# Signal only allows editing or deleting messages for 24 hours, after that the bot forgets who
# sent each broadcast
BROADCAST_RETENTION = timedelta(days=1)
# How long the messages between users and admins can be quoted to reply, or to ban their sender
CONVERSATION_RETENTION = timedelta(days=7)


class BroadcastBot:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

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

        self.db = Database(settings.db_path, settings.data_dir)
        if settings.password is not None:
            # Hashed again on every start, so changing the env var changes the password
            self.db.set_password_hash(hash_password(settings.password.get_secret_value()))

        # 0 disables disappearing messages
        self.expiration_time: int | None = settings.expiration_time or None

        # The pending retries of broadcasts that could not be sent to everyone, by author and timestamp of
        # the broadcast. Only kept in memory, they are lost on restart
        self.broadcast_retries: dict[tuple[str, int], BroadcastRetry] = {}

    def start(self) -> None:
        self.signal_bot.start()

    async def reply(self, ctx: DataMessageContext, text: str) -> SentMessage | None:
        """Replies to the message in `ctx`. Returns the reply, None if it could not be sent."""
        try:
            return await ctx.reply(SendMessage(text=text))
        except SignalBotError:
            logger.warning("Could not send a reply", exc_info=True)
            return None

    async def edit(self, message: SentMessage, text: str) -> None:
        """Changes the text of `message`, sent by the bot, keeping everything else. Does nothing if the
        text is the same."""
        if message.text == text:
            return
        new_message = SendMessage(**(message.model_dump(exclude={"recipient", "timestamp"}) | {"text": text}))
        try:
            await self.signal_bot.messages.edit(new_message, message)
        except SignalBotError:
            logger.warning("Could not edit a message", exc_info=True)

    async def send(
        self,
        recipient: str,
        text: str,
        attachments: list[str] | None = None,
        *,
        quote_timestamp: int | None = None,
        quote_author: str | None = None,
    ) -> int | None:
        """Sends `text` to `recipient`, optionally quoting a message in their chat with the bot. Returns the
        timestamp of the message, None if it could not be sent."""
        message = SendMessage(
            text=text,
            base64_attachments=attachments,
            quote_timestamp=quote_timestamp,
            quote_author=quote_author,
        )
        try:
            sent = await self.signal_bot.messages.send(message, recipient)
        except SignalBotError:
            logger.warning("Could not send a message", exc_info=True)
            logger.debug("Could not send a message to %s", recipient)
            return None
        return sent.timestamp

    async def notify_admins(self, text: str, *, exclude: tuple[str | None, ...] = ()) -> None:
        for admin in self.db.admins():
            if admin not in exclude:
                await self.send(admin, text)

    async def set_expiration_time(self, recipient: str) -> None:
        """Turns on disappearing messages in the chat with `recipient`, if enabled."""
        if self.expiration_time is None:
            return
        try:
            await self.signal_bot.contacts.update(UpdateContact(expiration_in_seconds=self.expiration_time), recipient)
        except SignalBotError:
            logger.warning("Could not set the disappearing messages timer", exc_info=True)

    async def forget_old_messages(self) -> None:
        """Run periodically, see `BROADCAST_RETENTION` and `CONVERSATION_RETENTION`."""
        now = now_ms()
        num_deleted = self.db.delete_deliveries_before(now - int(BROADCAST_RETENTION.total_seconds() * 1000))
        self.db.delete_expired_conversations(now - int(CONVERSATION_RETENTION.total_seconds() * 1000))
        logger.info("Forgot %s expired broadcast deliveries", num_deleted)

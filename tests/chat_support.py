"""Drives a real `BroadcastBot` through signal-cli envelopes with signalbot's HTTP clients mocked out.

Unlike signalbot's `mock_chat` decorator, a `Chat` can receive messages several times in one test, so a
test can quote a message that the bot sent earlier, e.g. to reply to a forwarded `!admin` message.
"""

from __future__ import annotations

import itertools
import json
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any
from unittest.mock import AsyncMock

from signalbot import SignalBotError
from signalbot._generated import RemoteDeleteResponse, SendMessageResponse
from signalbot.test_utils.chat_testing import (
    AboutMock,
    ChatTestCase,
    CheckSignalServiceMock,
    GetAllMock,
    ReceiveMock,
)

from signalblast.main import create_bot
from signalblast.settings import Settings

if TYPE_CHECKING:
    from pathlib import Path

    from pytest_mock import MockerFixture
    from signalbot._generated import RemoteDeleteRequest, SendMessageV2

    from signalblast.broadcastbot import BroadcastBot

SUBSCRIBER = "11111111-1111-1111-1111-111111111111"
OTHER_SUBSCRIBER = "22222222-2222-2222-2222-222222222222"
ADMIN = "33333333-3333-3333-3333-333333333333"
OTHER_ADMIN = "44444444-4444-4444-4444-444444444444"
STRANGER = "55555555-5555-5555-5555-555555555555"
ADMIN_PASSWORD = "correct horse battery staple"  # noqa: S105
ATTACHMENT_CONTENT = "aGVsbG8="
BOT = ChatTestCase.phone_number

# Unique timestamps, the bot uses them to tell messages apart
_received_timestamps = itertools.count(1_700_000_000_000)
_sent_timestamps = itertools.count(1_800_000_000_000)


@dataclass(frozen=True)
class Sent:
    """A message that the bot sent."""

    recipient: str
    text: str | None
    timestamp: int
    edit_timestamp: int | None
    attachments: list[str] | None
    quote_timestamp: int | None = None
    quote_author: str | None = None


def _envelope(source: str, timestamp: int, **body: object) -> str:
    return json.dumps(
        {
            "account": ChatTestCase.phone_number,
            "envelope": {
                "source": source,
                "sourceNumber": None,
                "sourceUuid": source,
                "sourceName": "some_source_name",
                "sourceDevice": 1,
                "timestamp": timestamp,
                "serverReceivedTimestamp": timestamp,
                "serverDeliveredTimestamp": timestamp,
                **body,
            },
        },
    )


def _data_message(text: str | None, timestamp: int, **extra: object) -> dict[str, object]:
    return {"message": text, "timestamp": timestamp, "expiresInSeconds": 0, "viewOnce": False, **extra}


def message(
    text: str | None,
    *,
    source: str,
    quote: Sent | str | None = None,
    attachment: bool = False,
    group: bool = False,
) -> str:
    """A message from `source` to the bot, optionally quoting a message the bot sent them, or one of their own
    messages (an envelope from `message`)."""
    timestamp = next(_received_timestamps)
    extra: dict[str, Any] = {}
    if isinstance(quote, Sent):
        extra["quote"] = {
            "id": quote.timestamp,
            "author": BOT,
            "authorNumber": BOT,
            "text": quote.text,
        }
    elif quote is not None:
        quoted = json.loads(quote)["envelope"]
        extra["quote"] = {
            "id": quoted["timestamp"],
            "author": quoted["sourceUuid"],
            "authorUuid": quoted["sourceUuid"],
            "text": quoted["dataMessage"]["message"],
        }
    if attachment:
        extra["attachments"] = [
            {"contentType": "image/png", "id": "attachment-1", "filename": "a.png", "size": 5, "isVoiceNote": False},
        ]
    if group:
        extra["groupInfo"] = {"groupId": ChatTestCase.group_internal_id, "type": "DELIVER", "revision": 1}
    return _envelope(source, timestamp, dataMessage=_data_message(text, timestamp, **extra))


def edit(text: str, *, source: str, target_timestamp: int) -> str:
    timestamp = next(_received_timestamps)
    return _envelope(
        source,
        timestamp,
        editMessage={"targetSentTimestamp": target_timestamp, "dataMessage": _data_message(text, timestamp)},
    )


def remote_delete(*, source: str, target_timestamp: int) -> str:
    timestamp = next(_received_timestamps)
    return _envelope(
        source,
        timestamp,
        dataMessage=_data_message(None, timestamp, remoteDelete={"timestamp": target_timestamp}),
    )


def timestamp_of(envelope: str) -> int:
    return json.loads(envelope)["envelope"]["timestamp"]


class Chat:
    def __init__(self, mocker: MockerFixture, tmp_path: Path) -> None:
        self.tmp_path = tmp_path
        self.sent: list[Sent] = []
        self.deleted: list[tuple[str, int]] = []
        # Recipients that the bot can't send messages to
        self.unreachable: set[str] = set()

        mocker.patch("signalbot._client.messages.MessagesClient.send", side_effect=self._send)
        mocker.patch("signalbot._client.messages.MessagesClient.remote_delete", side_effect=self._remote_delete)
        self.receive = mocker.patch("signalbot._client.messages.MessagesClient.receive", new_callable=ReceiveMock)
        mocker.patch("signalbot._client.groups.GroupsClient.get_all", new_callable=GetAllMock)
        mocker.patch("signalbot._client.general.GeneralClient.about", new_callable=AboutMock)
        mocker.patch("signalbot._client.SignalAPI.check_signal_service", new_callable=CheckSignalServiceMock)
        mocker.patch("signalbot._client.receipts.ReceiptsClient.send", new_callable=AsyncMock)
        self.start_typing = mocker.patch(
            "signalbot._client.messages.MessagesClient.start_typing",
            new_callable=AsyncMock,
        )
        self.stop_typing = mocker.patch("signalbot._client.messages.MessagesClient.stop_typing", new_callable=AsyncMock)
        self.update_contact = mocker.patch("signalbot._client.contacts.ContactsClient.update", new_callable=AsyncMock)
        mocker.patch(
            "signalbot._client.attachments.AttachmentsClient.download",
            new_callable=AsyncMock,
            return_value=ATTACHMENT_CONTENT,
        )
        self.delete_attachment = mocker.patch(
            "signalbot._client.attachments.AttachmentsClient.delete",
            new_callable=AsyncMock,
        )
        mocker.patch("signalblast.commands.broadcast.SEND_DELAY_SECONDS", (0, 0))
        mocker.patch("signalblast.commands.broadcast.RESUME_TYPING_DELAY_SECONDS", 0)
        self.bot: BroadcastBot

    async def start(
        self,
        *,
        password: str | None = ADMIN_PASSWORD,
        subscribers: tuple[str, ...] = (),
        admins: tuple[str, ...] = (),
        **settings: Any,  # noqa: ANN401
    ) -> BroadcastBot:
        self.bot = create_bot(
            Settings(
                _env_file=None,  # pyright: ignore[reportCallIssue] -- never read a developer's .env in tests
                phone_number=ChatTestCase.phone_number,
                signal_service=ChatTestCase.signal_service,
                data_dir=self.tmp_path,
                password=password,
                expiration_time=settings.pop("expiration_time", 0),
                **settings,
            ),
        )
        for subscriber in subscribers:
            self.bot.db.add_subscriber(subscriber)
        for admin in admins:
            self.bot.db.add_admin(admin)

        self.receive.define_raw([])
        await self.bot.signal_bot._async_post_init()  # noqa: SLF001
        # Messages are processed one by one in `send` instead of by signalbot's background tasks
        await self.bot.signal_bot._pipeline.stop()  # noqa: SLF001
        return self.bot

    async def send(self, *envelopes: str) -> list[Sent]:
        """Delivers `envelopes` to the bot and waits until they are handled. Returns what the bot sent."""
        num_sent = len(self.sent)
        self.receive.define_raw(list(envelopes))
        pipeline = self.bot.signal_bot._pipeline  # noqa: SLF001
        await pipeline._produce(1)  # noqa: SLF001
        while pipeline._q.qsize() > 0:  # noqa: SLF001
            await pipeline._consume_new_item(1)  # noqa: SLF001
        return self.sent[num_sent:]

    def texts_to(self, recipient: str) -> list[str | None]:
        return [sent.text for sent in self.sent if sent.recipient == recipient]

    def last_to(self, recipient: str) -> Sent:
        return [sent for sent in self.sent if sent.recipient == recipient][-1]

    async def _send(self, request: SendMessageV2) -> list[SendMessageResponse]:
        [recipient] = request.recipients
        if recipient in self.unreachable:
            raise SignalBotError(recipient)
        timestamp = next(_sent_timestamps)
        self.sent.append(
            Sent(
                recipient,
                request.message,
                timestamp,
                request.edit_timestamp,
                request.base64_attachments,
                request.quote_timestamp,
                request.quote_author,
            ),
        )
        # One response per recipient
        return [SendMessageResponse(timestamp=str(timestamp))]

    async def _remote_delete(self, request: RemoteDeleteRequest) -> RemoteDeleteResponse:
        self.deleted.append((request.recipient, request.timestamp))
        return RemoteDeleteResponse(timestamp=str(next(_sent_timestamps)))

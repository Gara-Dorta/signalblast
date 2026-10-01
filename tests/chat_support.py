"""Shared harness for exercising signalblast's command handlers through
signalbot's `ChatTestCase`/`mock_chat` mock chat infrastructure.

signalblast wraps signalbot's `SignalBot` in `BroadcastBot`, which swaps in its
own sqlite-backed storage and needs `load_data()` to run before handlers can
be registered. Most public commands (subscribe, broadcast, admin management,
...) are registered for direct/contact messages only, whereas `ChatTestCase`'s
built-in `new_message()` always builds a group message. `BroadcastChatTestCase`
below adds a private-message envelope builder and registers the extra client
stubs (read receipts, typing indicators) that signalblast's handlers touch on
every message but that signalbot's own `mock_chat` doesn't stub.
"""

from __future__ import annotations

import functools
import json
import time
import uuid
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock

from signalbot import ChatTestCase
from signalbot.test_utils.chat_testing import (
    AboutMock,
    CheckSignalServiceMock,
    GetAllMock,
    ReactMock,
    ReceiveMock,
    SendMock,
)

from signalblast.broadcastbot import BroadcastBot
from signalblast.settings import Settings

if TYPE_CHECKING:
    from pathlib import Path
    from typing import Protocol

    from pytest_mock import MockerFixture
    from signalbot._generated import SendMessageV2, SendReactionRequest

    class SendMockLike(Protocol):
        """Structural stand-in for `SendMock`.

        Pyright special-cases `unittest.mock`: a bare attribute declaration
        (`x: SomeMock`, no assignment in the class body) whose type derives from
        `unittest.mock.Mock` is always widened to `Any`, regardless of `SomeMock`'s
        own typing — confirmed independent of `signalbot` shipping `py.typed`.
        `send_mock`/`react_mock` on `BroadcastChatTestCase` are only ever assigned
        by the free `wrapper` function in `mock_broadcast_chat`, not by a method
        defined in the class body, so pyright can't infer them from an `__init__`
        assignment either. Declaring them against a plain (non-Mock) Protocol here
        sidesteps the special-casing so `call_count`/`results()` resolve for real.
        """

        call_count: int

        def results(self) -> list[SendMessageV2]: ...

    class ReactMockLike(Protocol):
        call_count: int

        def results(self) -> list[SendReactionRequest]: ...


AsyncTestMethod = Callable[..., Awaitable[None]]


def _patch_react(mocker: MockerFixture) -> ReactMock:
    # `MockerFixture.patch` is typed as returning a plain `MagicMock` regardless of
    # `new_callable`, which would erase `ReactMock`'s type (and e.g. `call_count`)
    # from `self.react_mock` in tests. Give the call site its real return type here.
    return mocker.patch(
        "signalbot._client.reactions.ReactionsClient.react",
        new_callable=ReactMock,
    )


def _patch_send(mocker: MockerFixture) -> SendMock:
    return mocker.patch(
        "signalbot._client.messages.MessagesClient.send",
        new_callable=SendMock,
    )


# Fixed uuids so tests can seed subscriber/admin/ban state before a chat
# message is "received" and then reference that exact sender in the message.
SUBSCRIBER_UUID = "11111111-1111-1111-1111-111111111111"
OTHER_SUBSCRIBER_UUID = "22222222-2222-2222-2222-222222222222"
ADMIN_UUID = "33333333-3333-3333-3333-333333333333"
STRANGER_UUID = "44444444-4444-4444-4444-444444444444"


def _private_envelope(*, source_uuid: str, timestamp: int, **envelope_body: object) -> str:
    """Wrap `envelope_body` (e.g. a `dataMessage` or `editMessage`) in a raw signal-cli
    envelope for a direct (non-group) message from `source_uuid`."""
    envelope = {
        "account": ChatTestCase.phone_number,
        "envelope": {
            "source": source_uuid,
            "sourceNumber": None,
            "sourceUuid": source_uuid,
            "sourceName": "some_source_name",
            "sourceDevice": 1,
            "timestamp": timestamp,
            "serverReceivedTimestamp": timestamp,
            "serverDeliveredTimestamp": timestamp,
            **envelope_body,
        },
    }
    return json.dumps(envelope)


def _data_message(text: str | None, timestamp: int, **extra: object) -> dict[str, object]:
    return {"message": text, "timestamp": timestamp, "expiresInSeconds": 0, "viewOnce": False, **extra}


def new_private_message(text: str, *, source_uuid: str) -> str:
    """Build a raw signal-cli envelope for a direct (non-group) message, as sent
    by a subscriber talking to the bot one-on-one."""
    timestamp = int(time.time() * 1000)
    return _private_envelope(source_uuid=source_uuid, timestamp=timestamp, dataMessage=_data_message(text, timestamp))


def new_private_edit(text: str, *, source_uuid: str, target_sent_timestamp: int) -> str:
    """Build a raw signal-cli envelope for an edit of an earlier direct message."""
    timestamp = int(time.time() * 1000)
    return _private_envelope(
        source_uuid=source_uuid,
        timestamp=timestamp,
        editMessage={"targetSentTimestamp": target_sent_timestamp, "dataMessage": _data_message(text, timestamp)},
    )


def new_private_remote_delete(*, source_uuid: str, target_sent_timestamp: int) -> str:
    """Build a raw signal-cli envelope for a delete-for-everyone of an earlier direct message."""
    timestamp = int(time.time() * 1000)
    return _private_envelope(
        source_uuid=source_uuid,
        timestamp=timestamp,
        dataMessage=_data_message(None, timestamp, remoteDelete={"timestamp": target_sent_timestamp}),
    )


def mock_broadcast_chat(*raw_messages: str) -> Callable[[AsyncTestMethod], AsyncTestMethod]:
    """Like signalbot's `mock_chat`, but takes raw envelope strings (so private
    messages built with `new_private_message` and friends can be used)
    and additionally stubs the read-receipt and typing-indicator endpoints that
    every signalblast command handler touches."""

    def decorator(func: AsyncTestMethod) -> AsyncTestMethod:
        @functools.wraps(func)
        async def wrapper(
            self: BroadcastChatTestCase,
            mocker: MockerFixture,
            *args: object,
            **kwargs: object,
        ) -> None:
            self.react_mock = _patch_react(mocker)
            self.send_mock = _patch_send(mocker)
            receive_mock = mocker.patch(
                "signalbot._client.messages.MessagesClient.receive",
                new_callable=ReceiveMock,
            )
            mocker.patch(
                "signalbot._client.groups.GroupsClient.get_all",
                new_callable=GetAllMock,
            )
            mocker.patch(
                "signalbot._client.general.GeneralClient.about",
                new_callable=AboutMock,
            )
            mocker.patch(
                "signalbot._client.SignalAPI.check_signal_service",
                new_callable=CheckSignalServiceMock,
            )
            mocker.patch(
                "signalbot._client.receipts.ReceiptsClient.send",
                new_callable=AsyncMock,
            )
            mocker.patch(
                "signalbot._client.messages.MessagesClient.start_typing",
                new_callable=AsyncMock,
            )
            mocker.patch(
                "signalbot._client.messages.MessagesClient.stop_typing",
                new_callable=AsyncMock,
            )

            receive_mock.define_raw(list(raw_messages))
            await self.signal_bot._async_post_init()  # noqa: SLF001

            # `_async_post_init` starts the real background produce/consume pipeline
            # on top of the same mocked (and endlessly re-iterable) message feed that
            # `run_bot()` below drains manually. For handlers that `await` for real
            # (e.g. Broadcast's anti-rate-limit sleeps between sends), that background
            # pipeline gets a chance to run too and re-delivers the same messages
            # concurrently. Tear it down so only the manual drive below processes them.
            await self.signal_bot._pipeline.stop()  # noqa: SLF001
            await self.run_bot()

            return await func(self, mocker, *args, **kwargs)

        return wrapper

    return decorator


class BroadcastChatTestCase(ChatTestCase):
    """`ChatTestCase` variant that builds signalblast's `BroadcastBot` instead of
    a bare `SignalBot`, keeping its sqlite storage confined to a pytest tmp
    path instead of touching the real `SIGNALBLAST_DATA_DIR`."""

    broadcast_bot: BroadcastBot

    # Narrows `ChatTestCase.send_mock: SendMock`/`react_mock: ReactMock` to the
    # `*Like` protocols (see the `TYPE_CHECKING` block above) so they resolve to
    # real types instead of `Any` in tests.
    if TYPE_CHECKING:
        # The actual assigned value is always a real `SendMock`/`ReactMock`, which
        # does satisfy these protocols; pyright's invariance check for mutable
        # attribute overrides is just being conservative here.
        send_mock: SendMockLike  # pyright: ignore[reportIncompatibleVariableOverride]
        react_mock: ReactMockLike  # pyright: ignore[reportIncompatibleVariableOverride]

    def setup_bot(
        self,
        tmp_path: Path,
        *,
        admin_pass: str | None = None,
        expiration_time: int = 0,
        welcome_message: str | None = None,
    ) -> None:
        settings = Settings(
            _env_file=None,  # pyright: ignore[reportCallIssue] -- never read a developer's .env in tests
            phone_number=ChatTestCase.phone_number,
            signal_service=ChatTestCase.signal_service,
            data_dir=tmp_path,
            password=admin_pass,
            expiration_time=expiration_time,
            **({"welcome_message": welcome_message} if welcome_message is not None else {}),
        )
        self.broadcast_bot = BroadcastBot(settings)
        self.signal_bot = self.broadcast_bot.signal_bot

    async def make_admin(self, admin_uuid: str) -> None:
        """Directly install `admin_uuid` as admin, bypassing the password check."""
        self.broadcast_bot.admin.admin_id = admin_uuid
        self.broadcast_bot.admin.save()

    @staticmethod
    def new_uuid() -> str:
        return str(uuid.uuid4())

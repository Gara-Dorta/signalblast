from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from chat_support import (
    OTHER_SUBSCRIBER_UUID,
    SUBSCRIBER_UUID,
    BroadcastChatTestCase,
    mock_broadcast_chat,
    new_private_edit,
    new_private_message,
    new_private_remote_delete,
)

from signalblast.commands import Broadcast

if TYPE_CHECKING:
    from pathlib import Path

    from pytest_mock import MockerFixture

BROADCAST_TEXT = "Hello everyone"
# One send per subscriber (2) plus the confirmation reply to the sender.
EXPECTED_BROADCAST_SEND_COUNT = 3


class TestBroadcast(BroadcastChatTestCase):
    @pytest.fixture(autouse=True)
    async def setup_fixture(self, tmp_path: Path) -> None:
        self.setup_bot(tmp_path)
        self.broadcast_bot.signal_bot.register(Broadcast(bot=self.broadcast_bot), groups=False)

    @pytest.fixture
    async def two_subscribers(self) -> None:
        # Seeded before the decorated message is delivered, since fixtures resolve
        # before `mock_broadcast_chat`'s wrapper runs the chat.
        await self.broadcast_bot.subscribers.add(SUBSCRIBER_UUID)
        await self.broadcast_bot.subscribers.add(OTHER_SUBSCRIBER_UUID)

    @pytest.fixture
    async def banned(self) -> None:
        await self.broadcast_bot.banned_users.add(SUBSCRIBER_UUID)

    @mock_broadcast_chat(new_private_message(BROADCAST_TEXT, source_uuid=SUBSCRIBER_UUID))
    async def test_broadcast_reaches_every_subscriber(self, mocker: MockerFixture, two_subscribers: None) -> None:
        # The sender is themselves a subscriber, so they get both a copy of the
        # broadcast and, afterwards, the confirmation reply.
        messages_by_recipient: dict[str, list[str]] = {}
        for sent in self.send_mock.results():
            messages_by_recipient.setdefault(sent.recipients[0], []).append(sent.message)

        assert messages_by_recipient[SUBSCRIBER_UUID][0] == BROADCAST_TEXT
        assert messages_by_recipient[OTHER_SUBSCRIBER_UUID] == [BROADCAST_TEXT]
        assert self.broadcast_bot.last_msg_user_uuid == SUBSCRIBER_UUID

    @mock_broadcast_chat(new_private_message(BROADCAST_TEXT, source_uuid=SUBSCRIBER_UUID))
    async def test_confirmation_excludes_the_sender_from_the_count(
        self,
        mocker: MockerFixture,
        two_subscribers: None,
    ) -> None:
        # `send_mock` records every `bot.messages.send` call, including the two
        # broadcasted copies and the final confirmation reply to the sender.
        assert self.send_mock.call_count == EXPECTED_BROADCAST_SEND_COUNT
        confirmation = self.send_mock.results()[-1]
        assert confirmation.recipients == [SUBSCRIBER_UUID]
        assert confirmation.message == "Message sent to 1 people"

    @mock_broadcast_chat(new_private_message(BROADCAST_TEXT, source_uuid=SUBSCRIBER_UUID))
    async def test_banned_sender_cannot_broadcast(self, mocker: MockerFixture, banned: None) -> None:
        [sent] = self.send_mock.results()
        assert sent.recipients == [SUBSCRIBER_UUID]
        assert sent.message == "This number is not allowed to send messages"

    @mock_broadcast_chat(new_private_message(BROADCAST_TEXT, source_uuid=SUBSCRIBER_UUID))
    async def test_non_subscriber_cannot_broadcast(self, mocker: MockerFixture) -> None:
        [sent] = self.send_mock.results()
        assert sent.recipients == [SUBSCRIBER_UUID]
        assert sent.message == self.broadcast_bot.must_subscribe_message


# A timestamp that never belonged to a broadcast, e.g. the subscriber's own `!help` message
NOT_A_BROADCAST_TIMESTAMP = 1_000
FOLLOW_UP_TEXT = "Is the bot still working?"


class TestEditAndDeleteOfNonBroadcasts(BroadcastChatTestCase):
    """Regression tests: editing or deleting a message that was never broadcast used to
    leave a lock acquired, so the next broadcast froze the whole bot."""

    @pytest.fixture(autouse=True)
    async def setup_fixture(self, tmp_path: Path) -> None:
        self.setup_bot(tmp_path)
        self.broadcast_bot.signal_bot.register(Broadcast(bot=self.broadcast_bot), groups=False)
        await self.broadcast_bot.subscribers.add(SUBSCRIBER_UUID)
        await self.broadcast_bot.subscribers.add(OTHER_SUBSCRIBER_UUID)

    def messages_to(self, recipient: str) -> list[str]:
        return [sent.message for sent in self.send_mock.results() if sent.recipients == [recipient]]

    @mock_broadcast_chat(
        new_private_edit(
            BROADCAST_TEXT,
            source_uuid=SUBSCRIBER_UUID,
            target_sent_timestamp=NOT_A_BROADCAST_TIMESTAMP,
        ),
        new_private_message(FOLLOW_UP_TEXT, source_uuid=SUBSCRIBER_UUID),
    )
    async def test_edit_of_non_broadcast_is_sent_as_new_broadcast(self, mocker: MockerFixture) -> None:
        assert all(sent.edit_timestamp is None for sent in self.send_mock.results())
        assert self.messages_to(OTHER_SUBSCRIBER_UUID) == [BROADCAST_TEXT, FOLLOW_UP_TEXT]
        assert self.messages_to(SUBSCRIBER_UUID)[-1] == "Message sent to 1 people"

    @mock_broadcast_chat(
        new_private_remote_delete(source_uuid=SUBSCRIBER_UUID, target_sent_timestamp=NOT_A_BROADCAST_TIMESTAMP),
        new_private_message(FOLLOW_UP_TEXT, source_uuid=SUBSCRIBER_UUID),
    )
    async def test_delete_of_non_broadcast_is_ignored(self, mocker: MockerFixture) -> None:
        assert self.messages_to(OTHER_SUBSCRIBER_UUID) == [FOLLOW_UP_TEXT]
        assert self.messages_to(SUBSCRIBER_UUID) == [FOLLOW_UP_TEXT, "Message sent to 1 people"]

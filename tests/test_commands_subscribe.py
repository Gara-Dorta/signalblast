from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from chat_support import (
    OTHER_SUBSCRIBER_UUID,
    SUBSCRIBER_UUID,
    BroadcastChatTestCase,
    mock_broadcast_chat,
    new_private_message,
)

from signalblast.commands import Subscribe, Unsubscribe

if TYPE_CHECKING:
    from pathlib import Path

    from pytest_mock import MockerFixture


class TestSubscribeUnsubscribe(BroadcastChatTestCase):
    @pytest.fixture(autouse=True)
    async def setup_fixture(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        await self.setup_bot(monkeypatch, tmp_path, welcome_message="Welcome aboard!")
        self.broadcast_bot.signal_bot.register(Subscribe(bot=self.broadcast_bot), groups=False)
        self.broadcast_bot.signal_bot.register(Unsubscribe(bot=self.broadcast_bot), groups=False)

    @pytest.fixture
    async def already_subscribed(self) -> None:
        # Seeded before the decorated message is delivered, since fixtures resolve
        # before `mock_broadcast_chat`'s wrapper runs the chat.
        await self.broadcast_bot.subscribers.add(SUBSCRIBER_UUID)

    @pytest.fixture
    async def banned(self) -> None:
        await self.broadcast_bot.banned_users.add(SUBSCRIBER_UUID)

    @pytest.fixture
    async def other_subscriber(self) -> None:
        await self.broadcast_bot.subscribers.add(OTHER_SUBSCRIBER_UUID)

    @mock_broadcast_chat(new_private_message("!subscribe", source_uuid=SUBSCRIBER_UUID))
    async def test_subscribe_adds_new_subscriber(self, mocker: MockerFixture) -> None:
        assert SUBSCRIBER_UUID in self.broadcast_bot.subscribers
        assert self.send_mock.call_count == 1
        [sent] = self.send_mock.results()
        assert sent.recipients == [SUBSCRIBER_UUID]
        assert sent.message == "Welcome aboard!"

    @mock_broadcast_chat(new_private_message("!subscribe", source_uuid=SUBSCRIBER_UUID))
    async def test_subscribing_twice_warns_already_subscribed(
        self,
        mocker: MockerFixture,
        already_subscribed: None,
    ) -> None:
        [sent] = self.send_mock.results()
        assert sent.message == "Already subscribed!"

    @mock_broadcast_chat(new_private_message("!subscribe", source_uuid=SUBSCRIBER_UUID))
    async def test_banned_user_cannot_subscribe(self, mocker: MockerFixture, banned: None) -> None:
        assert SUBSCRIBER_UUID not in self.broadcast_bot.subscribers
        [sent] = self.send_mock.results()
        assert sent.message == "This number is not allowed to subscribe"

    @mock_broadcast_chat(new_private_message("!unsubscribe", source_uuid=SUBSCRIBER_UUID))
    async def test_unsubscribe_removes_subscriber(self, mocker: MockerFixture, already_subscribed: None) -> None:
        assert SUBSCRIBER_UUID not in self.broadcast_bot.subscribers
        [sent] = self.send_mock.results()
        assert sent.message == "Successfully unsubscribed!"

    @mock_broadcast_chat(new_private_message("!unsubscribe", source_uuid=SUBSCRIBER_UUID))
    async def test_unsubscribe_when_not_subscribed(self, mocker: MockerFixture) -> None:
        [sent] = self.send_mock.results()
        assert sent.message == "Not subscribed!"

    @mock_broadcast_chat(new_private_message("!subscribe", source_uuid=SUBSCRIBER_UUID))
    async def test_subscribe_does_not_affect_other_subscribers(
        self,
        mocker: MockerFixture,
        other_subscriber: None,
    ) -> None:
        assert SUBSCRIBER_UUID in self.broadcast_bot.subscribers
        assert OTHER_SUBSCRIBER_UUID in self.broadcast_bot.subscribers

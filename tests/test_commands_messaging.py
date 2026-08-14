from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from chat_support import (
    ADMIN_UUID,
    STRANGER_UUID,
    SUBSCRIBER_UUID,
    BroadcastChatTestCase,
    mock_broadcast_chat,
    new_private_message,
)

from signalblast.commands import DisplayHelp, MessageFromAdmin, MessageToAdmin

if TYPE_CHECKING:
    from pathlib import Path

    from pytest_mock import MockerFixture

ADMIN_PASSWORD = "correct horse battery staple"  # noqa: S105


class TestMessageToAdminWithAdmin(BroadcastChatTestCase):
    @pytest.fixture(autouse=True)
    async def setup_fixture(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        await self.setup_bot(monkeypatch, tmp_path, admin_pass=ADMIN_PASSWORD)
        self.broadcast_bot.signal_bot.register(MessageToAdmin(bot=self.broadcast_bot), groups=True)
        await self.make_admin(ADMIN_UUID)

    @pytest.fixture
    async def banned(self) -> None:
        # Seeded before the decorated message is delivered, since fixtures resolve
        # before `mock_broadcast_chat`'s wrapper runs the chat.
        await self.broadcast_bot.banned_users.add(SUBSCRIBER_UUID)

    @mock_broadcast_chat(new_private_message("!admin Please help", source_uuid=SUBSCRIBER_UUID))
    async def test_message_is_forwarded_to_admin(self, mocker: MockerFixture) -> None:
        results_by_recipient = {sent.recipients[0]: sent.message for sent in self.send_mock.results()}
        assert SUBSCRIBER_UUID in results_by_recipient[ADMIN_UUID]
        assert "Please help" in results_by_recipient[ADMIN_UUID]
        assert results_by_recipient[SUBSCRIBER_UUID] == "Message sent to the admin"

    @mock_broadcast_chat(new_private_message("!admin Please help", source_uuid=SUBSCRIBER_UUID))
    async def test_banned_user_cannot_message_admin(self, mocker: MockerFixture, banned: None) -> None:
        [sent] = self.send_mock.results()
        assert sent.message == "You are not allowed to contact the admin!"


class TestMessageToAdminWithoutAdmin(BroadcastChatTestCase):
    @pytest.fixture(autouse=True)
    async def setup_fixture(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        await self.setup_bot(monkeypatch, tmp_path)
        self.broadcast_bot.signal_bot.register(MessageToAdmin(bot=self.broadcast_bot), groups=True)

    @mock_broadcast_chat(new_private_message("!admin Please help", source_uuid=SUBSCRIBER_UUID))
    async def test_warns_when_there_is_no_admin(self, mocker: MockerFixture) -> None:
        [sent] = self.send_mock.results()
        assert sent.message == "I'm sorry but there are no admins to contact!"


class TestMessageFromAdmin(BroadcastChatTestCase):
    @pytest.fixture(autouse=True)
    async def setup_fixture(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        await self.setup_bot(monkeypatch, tmp_path, admin_pass=ADMIN_PASSWORD)
        self.broadcast_bot.signal_bot.register(MessageFromAdmin(bot=self.broadcast_bot), groups=True)
        await self.make_admin(ADMIN_UUID)

    @pytest.fixture
    async def already_subscribed(self) -> None:
        await self.broadcast_bot.subscribers.add(SUBSCRIBER_UUID)

    @mock_broadcast_chat(new_private_message(f"!reply {SUBSCRIBER_UUID} Hello there", source_uuid=ADMIN_UUID))
    async def test_admin_messages_a_subscriber(self, mocker: MockerFixture, already_subscribed: None) -> None:
        results_by_recipient = {sent.recipients[0]: sent.message for sent in self.send_mock.results()}
        assert results_by_recipient[SUBSCRIBER_UUID] == "Admin: Hello there"
        assert results_by_recipient[ADMIN_UUID] == "Message sent"

    @mock_broadcast_chat(new_private_message(f"!reply {STRANGER_UUID} Hello there", source_uuid=ADMIN_UUID))
    async def test_messaging_a_non_subscriber_requires_force(self, mocker: MockerFixture) -> None:
        [sent] = self.send_mock.results()
        assert sent.message == "User is not in subscribers list, use !reply <uuid> !force to message them"

    @mock_broadcast_chat(new_private_message(f"!reply {STRANGER_UUID} !force Hello there", source_uuid=ADMIN_UUID))
    async def test_messaging_a_non_subscriber_with_force(self, mocker: MockerFixture) -> None:
        results_by_recipient = {sent.recipients[0]: sent.message for sent in self.send_mock.results()}
        assert results_by_recipient[STRANGER_UUID] == "Admin: Hello there"
        assert results_by_recipient[ADMIN_UUID] == "Message sent"

    @mock_broadcast_chat(new_private_message(f"!reply {SUBSCRIBER_UUID} Hello there", source_uuid=STRANGER_UUID))
    async def test_non_admin_cannot_message_subscribers(self, mocker: MockerFixture) -> None:
        results_by_recipient = {sent.recipients[0]: sent.message for sent in self.send_mock.results()}
        assert results_by_recipient[STRANGER_UUID] == "I'm sorry but you are not an admin"


class TestDisplayHelp(BroadcastChatTestCase):
    @pytest.fixture(autouse=True)
    async def setup_fixture(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        await self.setup_bot(monkeypatch, tmp_path, admin_pass=ADMIN_PASSWORD)
        self.broadcast_bot.signal_bot.register(DisplayHelp(bot=self.broadcast_bot), groups=False)
        await self.make_admin(ADMIN_UUID)

    @mock_broadcast_chat(new_private_message("!help", source_uuid=SUBSCRIBER_UUID))
    async def test_subscriber_gets_the_public_help_message(self, mocker: MockerFixture) -> None:
        [sent] = self.send_mock.results()
        assert sent.message == self.broadcast_bot.help_message
        assert "!add admin" not in sent.message

    @mock_broadcast_chat(new_private_message("!help", source_uuid=ADMIN_UUID))
    async def test_admin_gets_the_admin_help_message(self, mocker: MockerFixture) -> None:
        [sent] = self.send_mock.results()
        assert sent.message == self.broadcast_bot.admin_help_message
        assert "!add admin" in sent.message

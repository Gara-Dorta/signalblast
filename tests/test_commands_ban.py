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

from signalblast.commands import BanSubscriber, LiftBanSubscriber

if TYPE_CHECKING:
    from pathlib import Path

    from pytest_mock import MockerFixture

ADMIN_PASSWORD = "correct horse battery staple"  # noqa: S105


class TestBanLiftBan(BroadcastChatTestCase):
    @pytest.fixture(autouse=True)
    async def setup_fixture(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        await self.setup_bot(monkeypatch, tmp_path, admin_pass=ADMIN_PASSWORD)
        self.broadcast_bot.signal_bot.register(BanSubscriber(bot=self.broadcast_bot), groups=False)
        self.broadcast_bot.signal_bot.register(LiftBanSubscriber(bot=self.broadcast_bot), groups=False)
        await self.make_admin(ADMIN_UUID)

    @pytest.fixture
    async def already_subscribed(self) -> None:
        # Seeded before the decorated message is delivered, since fixtures resolve
        # before `mock_broadcast_chat`'s wrapper runs the chat.
        await self.broadcast_bot.subscribers.add(SUBSCRIBER_UUID)

    @pytest.fixture
    async def already_banned(self) -> None:
        await self.broadcast_bot.banned_users.add(SUBSCRIBER_UUID)

    @mock_broadcast_chat(new_private_message(f"!ban {SUBSCRIBER_UUID}", source_uuid=ADMIN_UUID))
    async def test_admin_bans_a_subscriber(self, mocker: MockerFixture, already_subscribed: None) -> None:
        assert SUBSCRIBER_UUID not in self.broadcast_bot.subscribers
        assert SUBSCRIBER_UUID in self.broadcast_bot.banned_users
        results_by_recipient = {sent.recipients[0]: sent.message for sent in self.send_mock.results()}
        assert results_by_recipient[SUBSCRIBER_UUID] == "You have been banned"
        assert results_by_recipient[ADMIN_UUID] == "Successfully banned user"

    @mock_broadcast_chat(new_private_message(f"!ban {SUBSCRIBER_UUID}", source_uuid=STRANGER_UUID))
    async def test_non_admin_cannot_ban(self, mocker: MockerFixture) -> None:
        assert SUBSCRIBER_UUID not in self.broadcast_bot.banned_users
        results_by_recipient = {sent.recipients[0]: sent.message for sent in self.send_mock.results()}
        assert results_by_recipient[STRANGER_UUID] == "I'm sorry but you are not an admin"
        assert "Tried to !ban" in results_by_recipient[ADMIN_UUID]

    @mock_broadcast_chat(new_private_message(f"!lift ban {SUBSCRIBER_UUID}", source_uuid=ADMIN_UUID))
    async def test_admin_lifts_ban(self, mocker: MockerFixture, already_banned: None) -> None:
        assert SUBSCRIBER_UUID not in self.broadcast_bot.banned_users
        results_by_recipient = {sent.recipients[0]: sent.message for sent in self.send_mock.results()}
        assert results_by_recipient[SUBSCRIBER_UUID] == "You have banned have been lifted, try subscribing again"
        assert results_by_recipient[ADMIN_UUID] == "Successfully lifted the ban on the user"

    @mock_broadcast_chat(new_private_message(f"!lift ban {SUBSCRIBER_UUID}", source_uuid=ADMIN_UUID))
    async def test_lifting_ban_on_a_user_not_banned(self, mocker: MockerFixture) -> None:
        assert self.send_mock.call_count == 1
        [sent] = self.send_mock.results()
        assert sent.message == "Could not lift the ban because the user was not banned"

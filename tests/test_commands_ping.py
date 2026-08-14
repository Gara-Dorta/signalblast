from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from chat_support import (
    ADMIN_UUID,
    STRANGER_UUID,
    BroadcastChatTestCase,
    mock_broadcast_chat,
    new_group_message,
)
from signalbot import ChatTestCase

from signalblast.commands import SetPing, UnsetPing

if TYPE_CHECKING:
    from pathlib import Path

    from pytest_mock import MockerFixture

ADMIN_PASSWORD = "correct horse battery staple"  # noqa: S105


class TestSetUnsetPing(BroadcastChatTestCase):
    @pytest.fixture(autouse=True)
    async def setup_fixture(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        await self.setup_bot(monkeypatch, tmp_path, admin_pass=ADMIN_PASSWORD)
        self.broadcast_bot.signal_bot.register(SetPing(bot=self.broadcast_bot), contacts=False, groups=True)
        self.broadcast_bot.signal_bot.register(UnsetPing(bot=self.broadcast_bot), contacts=False, groups=True)
        await self.make_admin(ADMIN_UUID)

    @mock_broadcast_chat(new_group_message("!set ping 60", source_uuid=ADMIN_UUID))
    async def test_admin_sets_the_ping_interval(self, mocker: MockerFixture) -> None:
        assert self.broadcast_bot.ping_job is not None
        assert self.broadcast_bot.db.get_ping() == (ChatTestCase.group_internal_id, 60)
        [sent] = self.send_mock.results()
        assert sent.recipients == [ChatTestCase.group_id]
        assert sent.message == "Ping set every 60 seconds"

    @mock_broadcast_chat(new_group_message("!set ping 60", source_uuid=STRANGER_UUID))
    async def test_non_admin_cannot_set_ping(self, mocker: MockerFixture) -> None:
        assert self.broadcast_bot.ping_job is None
        results = [sent.message for sent in self.send_mock.results()]
        assert "I'm sorry but you are not an admin" in results

    @pytest.fixture
    async def ping_already_set(self) -> None:
        # Seeded before the decorated message is delivered, since fixtures resolve
        # before `mock_broadcast_chat`'s wrapper runs the chat.
        self.broadcast_bot.schedule_ping(ChatTestCase.group_internal_id, 30)

    @mock_broadcast_chat(new_group_message("!unset ping", source_uuid=ADMIN_UUID))
    async def test_admin_unsets_the_ping(self, mocker: MockerFixture, ping_already_set: None) -> None:
        assert self.broadcast_bot.ping_job is None
        assert self.broadcast_bot.db.get_ping() is None
        [sent] = self.send_mock.results()
        assert sent.message == "Ping unset!"

    @mock_broadcast_chat(new_group_message("!unset ping", source_uuid=ADMIN_UUID))
    async def test_unset_ping_when_none_was_set(self, mocker: MockerFixture) -> None:
        [sent] = self.send_mock.results()
        assert sent.message == "Cannot unset because ping was not set!"

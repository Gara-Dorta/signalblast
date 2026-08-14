from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from chat_support import (
    ADMIN_UUID,
    STRANGER_UUID,
    BroadcastChatTestCase,
    mock_broadcast_chat,
    new_private_message,
)
from signalbot import __version__ as signalbot_version

from signalblast import __version__ as signalblast_version
from signalblast.commands import AddAdmin, LastMsgUserUuid, RemoveAdmin, ShowVersion

if TYPE_CHECKING:
    from pathlib import Path

    from pytest_mock import MockerFixture

ADMIN_PASSWORD = "correct horse battery staple"  # noqa: S105


class TestAddRemoveAdmin(BroadcastChatTestCase):
    @pytest.fixture(autouse=True)
    async def setup_fixture(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        await self.setup_bot(monkeypatch, tmp_path, admin_pass=ADMIN_PASSWORD)
        self.broadcast_bot.signal_bot.register(AddAdmin(bot=self.broadcast_bot), groups=False)
        self.broadcast_bot.signal_bot.register(RemoveAdmin(bot=self.broadcast_bot), groups=False)

    @mock_broadcast_chat(new_private_message(f"!add admin {ADMIN_PASSWORD}", source_uuid=ADMIN_UUID))
    async def test_add_admin_with_correct_password(self, mocker: MockerFixture) -> None:
        assert self.broadcast_bot.admin.admin_id == ADMIN_UUID
        [sent] = self.send_mock.results()
        assert sent.recipients == [ADMIN_UUID]
        assert sent.message == "You have been added as admin!"

    @mock_broadcast_chat(new_private_message("!add admin wrong password", source_uuid=ADMIN_UUID))
    async def test_add_admin_with_wrong_password(self, mocker: MockerFixture) -> None:
        assert self.broadcast_bot.admin.admin_id is None
        [sent] = self.send_mock.results()
        assert sent.message == "Adding failed, admin password is incorrect!"

    @pytest.fixture
    async def existing_admin(self) -> None:
        # Seeded before the decorated message is delivered, since fixtures resolve
        # before `mock_broadcast_chat`'s wrapper runs the chat.
        await self.make_admin(ADMIN_UUID)

    @mock_broadcast_chat(new_private_message(f"!add admin {ADMIN_PASSWORD}", source_uuid=STRANGER_UUID))
    async def test_replacing_admin_notifies_previous_admin(
        self,
        mocker: MockerFixture,
        existing_admin: None,
    ) -> None:
        assert self.broadcast_bot.admin.admin_id == STRANGER_UUID
        results_by_recipient = {sent.recipients[0]: sent.message for sent in self.send_mock.results()}
        assert results_by_recipient[STRANGER_UUID] == "You have been added as admin!"
        assert "You are no longer an admin!" in results_by_recipient[ADMIN_UUID]

    @mock_broadcast_chat(new_private_message(f"!remove admin {ADMIN_PASSWORD}", source_uuid=ADMIN_UUID))
    async def test_remove_admin_with_correct_password(self, mocker: MockerFixture, existing_admin: None) -> None:
        assert self.broadcast_bot.admin.admin_id is None
        [sent] = self.send_mock.results()
        assert sent.message == "Admin has been removed!"

    @mock_broadcast_chat(new_private_message("!remove admin wrong password", source_uuid=STRANGER_UUID))
    async def test_remove_admin_with_wrong_password(self, mocker: MockerFixture, existing_admin: None) -> None:
        assert self.broadcast_bot.admin.admin_id == ADMIN_UUID
        results_by_recipient = {sent.recipients[0]: sent.message for sent in self.send_mock.results()}
        assert results_by_recipient[STRANGER_UUID] == "Removing failed: admin password is incorrect!"
        assert "Tried to remove you as admin" in results_by_recipient[ADMIN_UUID]


class TestShowVersionAndLastMsgUserUuid(BroadcastChatTestCase):
    @pytest.fixture(autouse=True)
    async def setup_fixture(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        await self.setup_bot(monkeypatch, tmp_path, admin_pass=ADMIN_PASSWORD)
        self.broadcast_bot.signal_bot.register(ShowVersion(bot=self.broadcast_bot), groups=False)
        self.broadcast_bot.signal_bot.register(LastMsgUserUuid(bot=self.broadcast_bot), groups=True)
        await self.make_admin(ADMIN_UUID)

    @mock_broadcast_chat(new_private_message("!version", source_uuid=ADMIN_UUID))
    async def test_show_version_reports_all_components(self, mocker: MockerFixture) -> None:
        [sent] = self.send_mock.results()
        assert f"signalblast: {signalblast_version}" in sent.message
        assert f"signalBot: {signalbot_version}" in sent.message
        assert "signal-cli-rest-api:" in sent.message

    @mock_broadcast_chat(new_private_message("!version", source_uuid=STRANGER_UUID))
    async def test_show_version_denied_for_non_admin(self, mocker: MockerFixture) -> None:
        results_by_recipient = {sent.recipients[0]: sent.message for sent in self.send_mock.results()}
        assert results_by_recipient[STRANGER_UUID] == "I'm sorry but you are not an admin"
        assert "Tried to !version" in results_by_recipient[ADMIN_UUID]

    @pytest.fixture
    async def last_broadcaster(self) -> None:
        # Seeded before the decorated message is delivered, since fixtures resolve
        # before `mock_broadcast_chat`'s wrapper runs the chat.
        self.broadcast_bot.last_msg_user_uuid = STRANGER_UUID

    @mock_broadcast_chat(new_private_message("!last msg user uuid", source_uuid=ADMIN_UUID))
    async def test_last_msg_user_uuid_reports_last_broadcaster(
        self,
        mocker: MockerFixture,
        last_broadcaster: None,
    ) -> None:
        [sent] = self.send_mock.results()
        assert sent.recipients == [ADMIN_UUID]
        assert STRANGER_UUID in sent.message

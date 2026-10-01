from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from chat_support import Chat

if TYPE_CHECKING:
    from pathlib import Path

    from pytest_mock import MockerFixture


@pytest.fixture
def chat(mocker: MockerFixture, tmp_path: Path) -> Chat:
    return Chat(mocker, tmp_path)

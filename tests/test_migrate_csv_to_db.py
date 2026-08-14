from __future__ import annotations

import csv
from typing import TYPE_CHECKING

import pytest

from signalblast.migrate_csv_to_db import migrate
from signalblast.storage import SignalblastStorage

if TYPE_CHECKING:
    from pathlib import Path


@pytest.fixture
def data_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("SIGNALBLAST_CONFIG_DIR", str(tmp_path))
    return tmp_path


def _write_users_csv(path: Path, uuids: list[str]) -> None:
    # The legacy CSV format also has a phone_number column; migration ignores it.
    with path.open("w") as f:
        writer = csv.DictWriter(f, fieldnames=["uuid", "phone_number"])
        writer.writeheader()
        for uuid in uuids:
            writer.writerow({"uuid": uuid, "phone_number": "+1111"})


def test_migrate_subscribers_and_banned_users(data_dir: Path) -> None:
    _write_users_csv(data_dir / "subscribers.csv", ["uuid-1", "uuid-2"])
    _write_users_csv(data_dir / "banned_users.csv", ["uuid-3"])

    migrate()

    storage = SignalblastStorage(data_dir / "signalblast.db")
    assert storage.user_exists("subscribers", "uuid-1")
    assert storage.user_exists("subscribers", "uuid-2")
    assert storage.user_exists("banned_users", "uuid-3")
    assert not storage.user_exists("subscribers", "uuid-3")


def test_migrate_admin(data_dir: Path) -> None:
    with (data_dir / "admin.txt").open("w") as f:
        f.write("admin-uuid\n")
        f.write("hashed-password")

    migrate()

    storage = SignalblastStorage(data_dir / "signalblast.db")
    assert storage.get_admin() == ("admin-uuid", b"hashed-password")


def test_migrate_admin_with_no_admin_set(data_dir: Path) -> None:
    with (data_dir / "admin.txt").open("w") as f:
        f.write("\n")
        f.write("")

    migrate()

    storage = SignalblastStorage(data_dir / "signalblast.db")
    assert storage.get_admin() == (None, b"")


def test_migrate_is_idempotent(data_dir: Path) -> None:
    _write_users_csv(data_dir / "subscribers.csv", ["uuid-1"])

    migrate()
    migrate()

    storage = SignalblastStorage(data_dir / "signalblast.db")
    assert storage.user_count("subscribers") == 1


def test_migrate_handles_missing_files(data_dir: Path) -> None:
    migrate()

    storage = SignalblastStorage(data_dir / "signalblast.db")
    assert storage.user_count("subscribers") == 0
    assert storage.user_count("banned_users") == 0
    assert storage.get_admin() is None

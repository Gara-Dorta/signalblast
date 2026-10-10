from __future__ import annotations

import csv
import pkgutil
import re
import sqlite3
from typing import TYPE_CHECKING

import pytest

from signalblast import migrations
from signalblast.database import Database
from signalblast.migrations import SCHEMA_VERSION, v1
from signalblast.migrations.apply import MIGRATIONS

if TYPE_CHECKING:
    from pathlib import Path


def write_users_csv(path: Path, uuids: list[str]) -> None:
    # The pre-v2 format also has a phone_number column, which is not imported
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["uuid", "phone_number"])
        writer.writeheader()
        for uuid in uuids:
            writer.writerow({"uuid": uuid, "phone_number": "+1111"})


def user_version(path: Path) -> int:
    with sqlite3.connect(path) as conn:
        return conn.execute("PRAGMA user_version").fetchone()[0]


def test_every_version_is_applied_in_order() -> None:
    # A new vN.py that is not added to MIGRATIONS would never be applied
    versions = [m.name for m in pkgutil.iter_modules(migrations.__path__) if re.fullmatch(r"v\d+", m.name)]
    expected = [f"signalblast.migrations.v{n}" for n in range(1, len(versions) + 1)]
    assert [migration.__name__ for migration in MIGRATIONS] == expected


def test_new_database(tmp_path: Path) -> None:
    db = Database(tmp_path / "signalblast.db", tmp_path)

    assert user_version(tmp_path / "signalblast.db") == SCHEMA_VERSION
    assert db.subscribers() == []
    assert db.password_hash() is None


def test_imports_the_csv_files_once(tmp_path: Path) -> None:
    write_users_csv(tmp_path / "subscribers.csv", ["uuid-1", "uuid-2"])
    write_users_csv(tmp_path / "banned_users.csv", ["uuid-3"])
    (tmp_path / "admin.txt").write_text("admin-uuid\n$2b$12$hash")

    db = Database(tmp_path / "signalblast.db", tmp_path)

    assert db.subscribers() == ["uuid-1", "uuid-2"]
    assert [ban.uuid for ban in db.bans()] == ["uuid-3"]
    assert db.admins() == ["admin-uuid"]
    assert db.password_hash() == b"$2b$12$hash"
    assert sorted(path.name for path in tmp_path.glob("*.migrated")) == [
        "admin.txt.migrated",
        "banned_users.csv.migrated",
        "subscribers.csv.migrated",
    ]

    # Files that appear later are not imported again
    db.close()
    write_users_csv(tmp_path / "subscribers.csv", ["uuid-4"])
    db = Database(tmp_path / "signalblast.db", tmp_path)
    assert db.subscribers() == ["uuid-1", "uuid-2"]


def test_imports_admin_txt_without_admin_or_password(tmp_path: Path) -> None:
    (tmp_path / "admin.txt").write_text("\n")

    db = Database(tmp_path / "signalblast.db", tmp_path)

    assert db.admins() == []
    assert db.password_hash() is None


def test_imports_the_development_database(tmp_path: Path) -> None:
    path = tmp_path / "signalblast.db"
    with sqlite3.connect(path) as conn:
        conn.executescript("""
            CREATE TABLE signalbot (key text unique, value text);
            CREATE TABLE subscribers (uuid TEXT PRIMARY KEY, created_at TEXT);
            CREATE TABLE banned_users (uuid TEXT PRIMARY KEY, banned_at TEXT);
            CREATE TABLE admin (id INTEGER PRIMARY KEY, admin_id TEXT, hashed_password BLOB NOT NULL);
            CREATE TABLE ping (id INTEGER PRIMARY KEY, group_id TEXT, interval_seconds INTEGER);
            CREATE TABLE last_broadcast (id INTEGER PRIMARY KEY, subscriber_uuid TEXT);
            CREATE TABLE broadcast_timestamps (author TEXT, timestamp INTEGER, broadcast_timestamps TEXT);
            INSERT INTO subscribers (uuid) VALUES ('uuid-1'), ('uuid-2');
            INSERT INTO banned_users (uuid) VALUES ('uuid-3');
            INSERT INTO admin VALUES (1, 'admin-uuid', X'2462');
        """)
    conn.close()

    db = Database(path, tmp_path)

    assert db.subscribers() == ["uuid-1", "uuid-2"]
    assert [ban.uuid for ban in db.bans()] == ["uuid-3"]
    assert db.admins() == ["admin-uuid"]
    assert db.password_hash() == b"$b"
    with sqlite3.connect(path) as check:
        tables = {row[0] for row in check.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
    assert not tables & {"signalbot", "admin", "ping", "last_broadcast", "broadcast_timestamps"}
    assert not any(table.startswith("dev_") for table in tables)


def test_upgrades_a_v1_database(tmp_path: Path) -> None:
    path = tmp_path / "signalblast.db"
    with sqlite3.connect(path) as conn:
        conn.executescript(v1.SQL)
        conn.executescript("""
            INSERT INTO subscribers (uuid, failed_sends) VALUES ('uuid-1', 2), ('uuid-2', 0);
            INSERT INTO banned_users (uuid, snippet) VALUES ('uuid-3', 'spam');
            INSERT INTO admins (uuid) VALUES ('admin-uuid');
            PRAGMA user_version = 1;
        """)
    conn.close()
    # Files that are not imported on an upgrade are left alone
    write_users_csv(tmp_path / "subscribers.csv", ["uuid-4"])

    db = Database(path, tmp_path)

    assert user_version(path) == SCHEMA_VERSION
    assert [(ban.id, ban.uuid, ban.snippet) for ban in db.bans()] == [(1, "uuid-3", "spam")]
    assert db.admins() == ["admin-uuid"]
    with sqlite3.connect(path) as check:
        assert check.execute("SELECT uuid, failed_sends FROM subscribers").fetchall() == [("uuid-1", 2), ("uuid-2", 0)]
        columns = {
            table: [row[1] for row in check.execute(f"PRAGMA table_info({table})")]
            for table in ("subscribers", "banned_users", "admins")
        }
    assert columns == {
        "subscribers": ["uuid", "failed_sends"],
        "banned_users": ["id", "uuid", "snippet"],
        "admins": ["uuid"],
    }
    assert (tmp_path / "subscribers.csv").exists()


def test_refuses_a_database_from_a_newer_version(tmp_path: Path) -> None:
    path = tmp_path / "signalblast.db"
    with sqlite3.connect(path) as conn:
        conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION + 1}")
    conn.close()

    with pytest.raises(RuntimeError, match="newer signalblast"):
        Database(path, tmp_path)


def test_failed_migration_is_rolled_back(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    write_users_csv(tmp_path / "subscribers.csv", ["uuid-1"])
    (tmp_path / "admin.txt").write_text("admin-uuid\nhash")

    def fail(*_args: object) -> None:
        raise sqlite3.OperationalError

    monkeypatch.setattr(v1, "_import_admin", fail)
    path = tmp_path / "signalblast.db"
    with pytest.raises(sqlite3.OperationalError):
        Database(path, tmp_path)

    # Nothing was written and the files are kept, so the next start retries the migration
    assert user_version(path) == 0
    with sqlite3.connect(path) as conn:
        assert conn.execute("SELECT name FROM sqlite_master").fetchall() == []
    assert (tmp_path / "subscribers.csv").exists()
    assert (tmp_path / "admin.txt").exists()

    monkeypatch.undo()
    assert Database(path, tmp_path).subscribers() == ["uuid-1"]

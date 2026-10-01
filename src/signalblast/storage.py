from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any, ClassVar

from signalbot import SQLiteStorage

from signalblast.utils import TimestampData

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path


class SignalblastStorage(SQLiteStorage):
    """Extends signalbot's key/value `SQLiteStorage` with the relational tables
    signalblast needs: subscribers, banned users, the admin singleton, the last
    broadcast sender, and the per-subscriber timestamps of each
    broadcast. signalbot's generic key/value interface (and its `signalbot` table)
    is unused.
    """

    def __init__(self, database: str | Path, **kwargs: Any) -> None:  # noqa: ANN401 -- forwarded to sqlite3.connect
        super().__init__(database, **kwargs)
        self._create_tables()

    def _create_tables(self) -> None:
        # Created unconditionally by `SQLiteStorage.__init__`, but unused: see `broadcast_timestamps`
        self._sqlite.execute("DROP TABLE IF EXISTS signalbot")
        self._sqlite.execute(
            "CREATE TABLE IF NOT EXISTS broadcast_timestamps ("
            "author TEXT NOT NULL, "
            "timestamp INTEGER NOT NULL, "
            "broadcast_timestamps TEXT NOT NULL, "
            "PRIMARY KEY (author, timestamp))",
        )
        self._sqlite.execute(
            "CREATE TABLE IF NOT EXISTS subscribers ("
            "uuid TEXT PRIMARY KEY, "
            "created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)",
        )
        self._sqlite.execute(
            "CREATE TABLE IF NOT EXISTS banned_users ("
            "uuid TEXT PRIMARY KEY, "
            "banned_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)",
        )
        self._sqlite.execute(
            "CREATE TABLE IF NOT EXISTS admin ("
            "id INTEGER PRIMARY KEY CHECK (id = 1), "
            "admin_id TEXT, "
            "hashed_password BLOB NOT NULL, "
            "updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)",
        )
        self._sqlite.execute(
            "CREATE TABLE IF NOT EXISTS last_broadcast ("
            "id INTEGER PRIMARY KEY CHECK (id = 1), "
            "subscriber_uuid TEXT NOT NULL, "
            "updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)",
        )
        self._sqlite.commit()

    # --- Broadcast timestamps ---

    def read_broadcast_timestamps(self, author: str, timestamp: int) -> TimestampData | None:
        """Returns None if `author` sent no broadcast at `timestamp` (e.g. it was a command or it has expired)."""
        row = self._sqlite.execute(
            "SELECT broadcast_timestamps FROM broadcast_timestamps WHERE author = ? AND timestamp = ?",
            [author, timestamp],
        ).fetchone()
        if row is None:
            return None
        return TimestampData(author=author, timestamp=timestamp, broadcast_timestamps=json.loads(row[0]))

    def save_broadcast_timestamps(self, data: TimestampData) -> None:
        self._sqlite.execute(
            "INSERT INTO broadcast_timestamps (author, timestamp, broadcast_timestamps) VALUES (?, ?, ?) "
            "ON CONFLICT(author, timestamp) DO UPDATE SET broadcast_timestamps=excluded.broadcast_timestamps",
            [data.author, data.timestamp, json.dumps(data.broadcast_timestamps)],
        )
        self._sqlite.commit()

    def delete_broadcast_timestamps_before(self, timestamp: int) -> int:
        """Deletes the broadcasts sent before `timestamp` (in ms). Returns how many were deleted."""
        cursor = self._sqlite.execute("DELETE FROM broadcast_timestamps WHERE timestamp < ?", [timestamp])
        self._sqlite.commit()
        return cursor.rowcount

    # --- Generic user tables (subscribers / banned_users) ---
    #
    # Queries are literal per-table strings (not f-string-interpolated) so ruff's S608
    # static SQL-injection check has nothing to flag: `table` is always one of these two
    # hardcoded keys, never user input.

    _ADD_USER_QUERIES: ClassVar[dict[str, str]] = {
        "subscribers": "INSERT OR IGNORE INTO subscribers (uuid) VALUES (?)",
        "banned_users": "INSERT OR IGNORE INTO banned_users (uuid) VALUES (?)",
    }
    _REMOVE_USER_QUERIES: ClassVar[dict[str, str]] = {
        "subscribers": "DELETE FROM subscribers WHERE uuid = ?",
        "banned_users": "DELETE FROM banned_users WHERE uuid = ?",
    }
    _USER_EXISTS_QUERIES: ClassVar[dict[str, str]] = {
        "subscribers": "SELECT EXISTS(SELECT 1 FROM subscribers WHERE uuid = ?)",
        "banned_users": "SELECT EXISTS(SELECT 1 FROM banned_users WHERE uuid = ?)",
    }
    _LIST_USER_UUIDS_QUERIES: ClassVar[dict[str, str]] = {
        "subscribers": "SELECT uuid FROM subscribers ORDER BY created_at",
        "banned_users": "SELECT uuid FROM banned_users ORDER BY banned_at",
    }
    _USER_COUNT_QUERIES: ClassVar[dict[str, str]] = {
        "subscribers": "SELECT COUNT(*) FROM subscribers",
        "banned_users": "SELECT COUNT(*) FROM banned_users",
    }

    def add_user(self, table: str, uuid: str) -> None:
        self._sqlite.execute(self._ADD_USER_QUERIES[table], [uuid])
        self._sqlite.commit()

    def remove_user(self, table: str, uuid: str) -> None:
        self._sqlite.execute(self._REMOVE_USER_QUERIES[table], [uuid])
        self._sqlite.commit()

    def user_exists(self, table: str, uuid: str) -> bool:
        row = self._sqlite.execute(self._USER_EXISTS_QUERIES[table], [uuid]).fetchone()
        return bool(row[0])

    def list_user_uuids(self, table: str) -> list[str]:
        rows = self._sqlite.execute(self._LIST_USER_UUIDS_QUERIES[table]).fetchall()
        return [row[0] for row in rows]

    def user_count(self, table: str) -> int:
        return self._sqlite.execute(self._USER_COUNT_QUERIES[table]).fetchone()[0]

    # --- Admin singleton ---

    def get_admin(self) -> tuple[str | None, bytes] | None:
        row = self._sqlite.execute("SELECT admin_id, hashed_password FROM admin WHERE id = 1").fetchone()
        if row is None:
            return None
        return row[0], row[1]

    def set_admin(self, admin_id: str | None, hashed_password: bytes) -> None:
        self._sqlite.execute(
            "INSERT INTO admin (id, admin_id, hashed_password) VALUES (1, ?, ?) "
            "ON CONFLICT(id) DO UPDATE SET admin_id=excluded.admin_id, "
            "hashed_password=excluded.hashed_password, updated_at=CURRENT_TIMESTAMP",
            [admin_id, hashed_password],
        )
        self._sqlite.commit()

    # --- Last broadcast singleton ---

    def get_last_broadcast_uuid(self) -> str | None:
        row = self._sqlite.execute("SELECT subscriber_uuid FROM last_broadcast WHERE id = 1").fetchone()
        return row[0] if row is not None else None

    def set_last_broadcast_uuid(self, subscriber_uuid: str) -> None:
        self._sqlite.execute(
            "INSERT INTO last_broadcast (id, subscriber_uuid) VALUES (1, ?) "
            "ON CONFLICT(id) DO UPDATE SET subscriber_uuid=excluded.subscriber_uuid, "
            "updated_at=CURRENT_TIMESTAMP",
            [subscriber_uuid],
        )
        self._sqlite.commit()


class UserTable:
    """Ergonomic view over one of `SignalblastStorage`'s user tables (subscribers or
    banned_users), preserving the `in`/`len`/`for ... in`/`add`/`remove` interface the
    command handlers already use."""

    def __init__(self, storage: SignalblastStorage, table: str) -> None:
        self._storage = storage
        self._table = table

    async def add(self, uuid: str) -> None:
        self._storage.add_user(self._table, uuid)

    async def remove(self, uuid: str) -> None:
        self._storage.remove_user(self._table, uuid)

    def __contains__(self, uuid: str) -> bool:
        return self._storage.user_exists(self._table, uuid)

    def __iter__(self) -> Iterator[str]:
        yield from self._storage.list_user_uuids(self._table)

    def __len__(self) -> int:
        return self._storage.user_count(self._table)

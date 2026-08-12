from __future__ import annotations

from collections.abc import Iterator
from typing import Any

from signalbot import SQLiteStorage


class SignalblastStorage(SQLiteStorage):
    """Extends signalbot's key/value `SQLiteStorage` with the relational tables
    signalblast needs: subscribers, banned users, the admin singleton, the active
    ping job, and the last broadcast sender. All tables live in the same sqlite
    file/connection as the inherited generic `signalbot` key/value table.
    """

    def __init__(self, database: Any, **kwargs: Any) -> None:  # noqa: ANN401
        super().__init__(database, **kwargs)
        self._create_tables()

    def _create_tables(self) -> None:
        self._sqlite.execute(
            "CREATE TABLE IF NOT EXISTS subscribers ("
            "uuid TEXT PRIMARY KEY, "
            "phone_number TEXT, "
            "created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)",
        )
        self._sqlite.execute(
            "CREATE TABLE IF NOT EXISTS banned_users ("
            "uuid TEXT PRIMARY KEY, "
            "phone_number TEXT, "
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
            "CREATE TABLE IF NOT EXISTS ping ("
            "id INTEGER PRIMARY KEY CHECK (id = 1), "
            "group_id TEXT NOT NULL, "
            "interval_seconds INTEGER NOT NULL, "
            "created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)",
        )
        self._sqlite.execute(
            "CREATE TABLE IF NOT EXISTS last_broadcast ("
            "id INTEGER PRIMARY KEY CHECK (id = 1), "
            "subscriber_uuid TEXT NOT NULL, "
            "updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)",
        )
        self._sqlite.commit()

    # --- Generic user tables (subscribers / banned_users) ---

    _USER_ORDER_COLUMN = {"subscribers": "created_at", "banned_users": "banned_at"}

    def add_user(self, table: str, uuid: str, phone_number: str | None) -> None:
        self._sqlite.execute(
            f"INSERT INTO {table} (uuid, phone_number) VALUES (?, ?) "  # noqa: S608
            "ON CONFLICT(uuid) DO UPDATE SET phone_number=excluded.phone_number",
            [uuid, phone_number],
        )
        self._sqlite.commit()

    def remove_user(self, table: str, uuid: str) -> None:
        self._sqlite.execute(f"DELETE FROM {table} WHERE uuid = ?", [uuid])  # noqa: S608
        self._sqlite.commit()

    def user_exists(self, table: str, uuid: str) -> bool:
        row = self._sqlite.execute(
            f"SELECT EXISTS(SELECT 1 FROM {table} WHERE uuid = ?)",  # noqa: S608
            [uuid],
        ).fetchone()
        return bool(row[0])

    def list_user_uuids(self, table: str) -> list[str]:
        order_column = self._USER_ORDER_COLUMN[table]
        rows = self._sqlite.execute(f"SELECT uuid FROM {table} ORDER BY {order_column}").fetchall()  # noqa: S608
        return [row[0] for row in rows]

    def user_count(self, table: str) -> int:
        return self._sqlite.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]  # noqa: S608

    def get_user_phone_number(self, table: str, uuid: str) -> str | None:
        row = self._sqlite.execute(f"SELECT phone_number FROM {table} WHERE uuid = ?", [uuid]).fetchone()  # noqa: S608
        return row[0] if row is not None else None

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

    # --- Ping singleton ---

    def get_ping(self) -> tuple[str, int] | None:
        row = self._sqlite.execute("SELECT group_id, interval_seconds FROM ping WHERE id = 1").fetchone()
        if row is None:
            return None
        return row[0], row[1]

    def set_ping(self, group_id: str, interval_seconds: int) -> None:
        self._sqlite.execute(
            "INSERT INTO ping (id, group_id, interval_seconds) VALUES (1, ?, ?) "
            "ON CONFLICT(id) DO UPDATE SET group_id=excluded.group_id, "
            "interval_seconds=excluded.interval_seconds, created_at=CURRENT_TIMESTAMP",
            [group_id, interval_seconds],
        )
        self._sqlite.commit()

    def clear_ping(self) -> None:
        self._sqlite.execute("DELETE FROM ping WHERE id = 1")
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

    async def add(self, uuid: str, phone_number: str | None) -> None:
        self._storage.add_user(self._table, uuid, phone_number)

    async def remove(self, uuid: str) -> None:
        self._storage.remove_user(self._table, uuid)

    def get_phone_number(self, uuid: str) -> str | None:
        return self._storage.get_user_phone_number(self._table, uuid)

    def __contains__(self, uuid: str) -> bool:
        return self._storage.user_exists(self._table, uuid)

    def __iter__(self) -> Iterator[str]:
        yield from self._storage.list_user_uuids(self._table)

    def __len__(self) -> int:
        return self._storage.user_count(self._table)

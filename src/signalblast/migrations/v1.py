"""v1: the schema released in v1.0.0, which every database is created with.

The data from older signalblast versions is imported into it: the `subscribers.csv`, `banned_users.csv`
and `admin.txt` files in the data directory, and the tables of the unversioned database used during the
v2 development.
"""

from __future__ import annotations

import csv
import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import sqlite3
    from pathlib import Path

logger = logging.getLogger(__name__)

SQL = """
CREATE TABLE subscribers (
    uuid TEXT PRIMARY KEY,
    subscribed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    failed_sends INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE banned_users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    uuid TEXT NOT NULL UNIQUE,
    banned_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    snippet TEXT
);
CREATE TABLE admins (
    uuid TEXT PRIMARY KEY,
    added_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE settings (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    admin_password_hash BLOB
);
INSERT INTO settings (id) VALUES (1);
CREATE TABLE broadcast_deliveries (
    author TEXT NOT NULL,
    broadcast_ts INTEGER NOT NULL,
    recipient TEXT NOT NULL,
    recipient_ts INTEGER NOT NULL,
    PRIMARY KEY (recipient, recipient_ts)
);
CREATE INDEX broadcast_deliveries_by_broadcast ON broadcast_deliveries (author, broadcast_ts);
CREATE INDEX broadcast_deliveries_by_age ON broadcast_deliveries (broadcast_ts);
CREATE TABLE conversation_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user TEXT NOT NULL,
    author TEXT NOT NULL,
    sent_at INTEGER NOT NULL
);
CREATE INDEX conversation_messages_by_age ON conversation_messages (sent_at);
CREATE TABLE conversation_copies (
    message_id INTEGER NOT NULL REFERENCES conversation_messages (id) ON DELETE CASCADE,
    chat TEXT NOT NULL,
    timestamp INTEGER NOT NULL,
    PRIMARY KEY (chat, timestamp)
);
CREATE INDEX conversation_copies_by_message ON conversation_copies (message_id, chat);
"""

# Tables of the unversioned database used during the v2 development
_DEV_TABLES = ("subscribers", "banned_users", "admin", "ping", "last_broadcast", "broadcast_timestamps", "signalbot")


def rename_dev_tables(conn: sqlite3.Connection) -> set[str]:
    """Moves the development tables out of the way of `SQL`, they reuse some of its table names."""
    existing = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
    dev_tables = existing.intersection(_DEV_TABLES)
    for table in dev_tables:
        conn.execute(f"ALTER TABLE {table} RENAME TO dev_{table}")
    return dev_tables


def import_old_data(conn: sqlite3.Connection, dev_tables: set[str], data_dir: Path | None) -> list[Path]:
    """Returns the files that were imported."""
    if dev_tables:
        _import_dev_tables(conn, dev_tables)
    return _import_csv_files(conn, data_dir) if data_dir is not None else []


def _import_dev_tables(conn: sqlite3.Connection, dev_tables: set[str]) -> None:
    if "subscribers" in dev_tables:
        conn.execute("INSERT OR IGNORE INTO subscribers (uuid) SELECT uuid FROM dev_subscribers ORDER BY rowid")
    if "banned_users" in dev_tables:
        conn.execute("INSERT OR IGNORE INTO banned_users (uuid) SELECT uuid FROM dev_banned_users ORDER BY rowid")
    if "admin" in dev_tables:
        row = conn.execute("SELECT admin_id, hashed_password FROM dev_admin WHERE id = 1").fetchone()
        if row is not None:
            _import_admin(conn, row[0], row[1])
    for table in dev_tables:
        conn.execute(f"DROP TABLE dev_{table}")
    logger.info("Imported the development database tables")


def _import_csv_files(conn: sqlite3.Connection, data_dir: Path) -> list[Path]:
    """Returns the files that were imported."""
    imported = []
    for name, table in (("subscribers.csv", "subscribers"), ("banned_users.csv", "banned_users")):
        path = data_dir / name
        if not path.exists():
            continue
        with path.open(newline="") as f:
            uuids = [(row["uuid"],) for row in csv.DictReader(f) if row.get("uuid")]
        # `table` is one of the two literals above
        conn.executemany(f"INSERT OR IGNORE INTO {table} (uuid) VALUES (?)", uuids)  # noqa: S608
        imported.append(path)

    admin_txt = data_dir / "admin.txt"
    if admin_txt.exists():
        # First line is the admin uuid (empty if there was none), second line the bcrypt hash
        lines = [*admin_txt.read_text().splitlines(), "", ""]
        _import_admin(conn, lines[0].strip() or None, lines[1].strip().encode())
        imported.append(admin_txt)
    return imported


def _import_admin(conn: sqlite3.Connection, admin_id: str | None, password_hash: bytes | None) -> None:
    """Keeps the admin and password that are already in the database, e.g. from the development tables."""
    if admin_id:
        conn.execute("INSERT OR IGNORE INTO admins (uuid) VALUES (?)", [admin_id])
    if password_hash:
        conn.execute(
            "UPDATE settings SET admin_password_hash = ? WHERE id = 1 AND admin_password_hash IS NULL",
            [password_hash],
        )

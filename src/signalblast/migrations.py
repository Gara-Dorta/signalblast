"""Creates and upgrades signalblast's database schema, tracked with sqlite's `user_version`.

The first time the database is created, the data from older signalblast versions is imported: the
`subscribers.csv`, `banned_users.csv` and `admin.txt` files in the data directory (renamed to
`*.migrated` afterwards), and the tables of the unversioned database used during the v2 development.
"""

from __future__ import annotations

import csv
import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import sqlite3
    from pathlib import Path

logger = logging.getLogger(__name__)

SCHEMA_VERSION = 1

_SCHEMA_V1 = """
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
CREATE TABLE pseudonyms (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    uuid TEXT NOT NULL UNIQUE,
    last_message_at INTEGER NOT NULL
);
CREATE TABLE admin_messages (
    admin TEXT NOT NULL,
    recipient_ts INTEGER NOT NULL,
    pseudonym_id INTEGER NOT NULL REFERENCES pseudonyms (id) ON DELETE CASCADE,
    sent_at INTEGER NOT NULL,
    PRIMARY KEY (admin, recipient_ts)
);
CREATE INDEX admin_messages_by_age ON admin_messages (sent_at);
"""

# Tables of the unversioned database used during the v2 development
_DEV_TABLES = ("subscribers", "banned_users", "admin", "ping", "last_broadcast", "broadcast_timestamps", "signalbot")

_CSV_FILES = ("subscribers.csv", "banned_users.csv", "admin.txt")


def migrate(conn: sqlite3.Connection, data_dir: Path | None) -> None:
    version = conn.execute("PRAGMA user_version").fetchone()[0]
    if version == SCHEMA_VERSION:
        return
    if version > SCHEMA_VERSION:
        msg = f"The database was created by a newer signalblast (schema {version}), please upgrade signalblast"
        raise RuntimeError(msg)

    conn.execute("BEGIN")
    try:
        dev_tables = _rename_dev_tables(conn)
        _create_v1(conn)
        if dev_tables:
            _import_dev_tables(conn, dev_tables)
        if data_dir is not None:
            _import_csv_files(conn, data_dir)
        conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
    except BaseException:
        conn.rollback()
        raise
    conn.commit()

    if data_dir is not None:
        for name in _CSV_FILES:
            path = data_dir / name
            if path.exists():
                path.rename(path.with_name(name + ".migrated"))
                logger.info("Imported %s into the database and renamed it to %s.migrated", name, name)


def _create_v1(conn: sqlite3.Connection) -> None:
    # `executescript` would commit the open transaction, run the statements one by one instead
    for statement in _SCHEMA_V1.split(";"):
        if statement.strip():
            conn.execute(statement)


def _rename_dev_tables(conn: sqlite3.Connection) -> set[str]:
    existing = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
    dev_tables = existing.intersection(_DEV_TABLES)
    for table in dev_tables:
        conn.execute(f"ALTER TABLE {table} RENAME TO dev_{table}")
    return dev_tables


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
    logger.info("Imported the development database tables into schema %s", SCHEMA_VERSION)


def _import_csv_files(conn: sqlite3.Connection, data_dir: Path) -> None:
    for name, table in (("subscribers.csv", "subscribers"), ("banned_users.csv", "banned_users")):
        path = data_dir / name
        if not path.exists():
            continue
        with path.open(newline="") as f:
            uuids = [(row["uuid"],) for row in csv.DictReader(f) if row.get("uuid")]
        # `table` is one of the two literals above
        conn.executemany(f"INSERT OR IGNORE INTO {table} (uuid) VALUES (?)", uuids)  # noqa: S608

    admin_txt = data_dir / "admin.txt"
    if admin_txt.exists():
        # First line is the admin uuid (empty if there was none), second line the bcrypt hash
        lines = [*admin_txt.read_text().splitlines(), "", ""]
        _import_admin(conn, lines[0].strip() or None, lines[1].strip().encode())


def _import_admin(conn: sqlite3.Connection, admin_id: str | None, password_hash: bytes | None) -> None:
    """Keeps the admin and password that are already in the database, e.g. from the development tables."""
    if admin_id:
        conn.execute("INSERT OR IGNORE INTO admins (uuid) VALUES (?)", [admin_id])
    if password_hash:
        conn.execute(
            "UPDATE settings SET admin_password_hash = ? WHERE id = 1 AND admin_password_hash IS NULL",
            [password_hash],
        )

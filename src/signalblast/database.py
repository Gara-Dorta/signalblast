from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from typing import TYPE_CHECKING

from signalblast.migrations import migrate

if TYPE_CHECKING:
    from collections.abc import Mapping
    from pathlib import Path


@dataclass(frozen=True)
class Ban:
    id: int
    uuid: str
    banned_at: str
    snippet: str | None


@dataclass(frozen=True)
class ForwardedMessageSender:
    """Who sent the `!admin` message that the bot forwarded to an admin."""

    uuid: str
    pseudonym_id: int


class Database:
    """signalblast's sqlite database, see `migrations.py` for the schema.

    Every method runs synchronously and commits before returning. It is only used from the event
    loop thread, so there are no concurrent writers.
    """

    def __init__(self, path: Path | str, data_dir: Path | None = None) -> None:
        """`data_dir` is where pre-v2 CSV files are looked for when the database is first created."""
        self._conn = sqlite3.connect(path)
        self._conn.execute("PRAGMA foreign_keys = ON")
        migrate(self._conn, data_dir)

    def close(self) -> None:
        self._conn.close()

    # --- Subscribers ---

    def add_subscriber(self, uuid: str) -> bool:
        """Returns False if `uuid` was already subscribed."""
        with self._conn:
            cursor = self._conn.execute("INSERT OR IGNORE INTO subscribers (uuid) VALUES (?)", [uuid])
        return cursor.rowcount == 1

    def remove_subscriber(self, uuid: str) -> bool:
        """Returns False if `uuid` was not subscribed."""
        with self._conn:
            cursor = self._conn.execute("DELETE FROM subscribers WHERE uuid = ?", [uuid])
        return cursor.rowcount == 1

    def is_subscriber(self, uuid: str) -> bool:
        return self._exists("SELECT 1 FROM subscribers WHERE uuid = ?", uuid)

    def subscribers(self) -> list[str]:
        return [row[0] for row in self._conn.execute("SELECT uuid FROM subscribers ORDER BY rowid")]

    def subscriber_count(self) -> int:
        return self._conn.execute("SELECT COUNT(*) FROM subscribers").fetchone()[0]

    def record_send_success(self, uuid: str) -> None:
        with self._conn:
            self._conn.execute("UPDATE subscribers SET failed_sends = 0 WHERE uuid = ? AND failed_sends != 0", [uuid])

    def record_send_failure(self, uuid: str) -> int:
        """Returns the number of consecutive failed sends to `uuid`, 0 if it is not subscribed."""
        with self._conn:
            row = self._conn.execute(
                "UPDATE subscribers SET failed_sends = failed_sends + 1 WHERE uuid = ? RETURNING failed_sends",
                [uuid],
            ).fetchone()
        return row[0] if row is not None else 0

    # --- Bans ---

    def ban(self, uuid: str, snippet: str | None) -> tuple[int, bool]:
        """Bans and unsubscribes `uuid`. Returns the ban number and False if it was already banned."""
        with self._conn:
            self._conn.execute("DELETE FROM subscribers WHERE uuid = ?", [uuid])
            cursor = self._conn.execute(
                "INSERT OR IGNORE INTO banned_users (uuid, snippet) VALUES (?, ?)",
                [uuid, snippet],
            )
            ban_id = self._conn.execute("SELECT id FROM banned_users WHERE uuid = ?", [uuid]).fetchone()[0]
        return ban_id, cursor.rowcount == 1

    def is_banned(self, uuid: str) -> bool:
        return self._exists("SELECT 1 FROM banned_users WHERE uuid = ?", uuid)

    def bans(self) -> list[Ban]:
        rows = self._conn.execute("SELECT id, uuid, banned_at, snippet FROM banned_users ORDER BY id")
        return [Ban(*row) for row in rows]

    def lift_ban(self, ban_id: int) -> str | None:
        """Returns the uuid of the user whose ban was lifted, None if there is no such ban."""
        with self._conn:
            row = self._conn.execute("DELETE FROM banned_users WHERE id = ? RETURNING uuid", [ban_id]).fetchone()
        return row[0] if row is not None else None

    # --- Admins ---

    def add_admin(self, uuid: str) -> bool:
        """Returns False if `uuid` was already an admin."""
        with self._conn:
            cursor = self._conn.execute("INSERT OR IGNORE INTO admins (uuid) VALUES (?)", [uuid])
        return cursor.rowcount == 1

    def remove_admin(self, uuid: str) -> bool:
        """Returns False if `uuid` was not an admin."""
        with self._conn:
            cursor = self._conn.execute("DELETE FROM admins WHERE uuid = ?", [uuid])
        return cursor.rowcount == 1

    def is_admin(self, uuid: str) -> bool:
        return self._exists("SELECT 1 FROM admins WHERE uuid = ?", uuid)

    def admins(self) -> list[str]:
        return [row[0] for row in self._conn.execute("SELECT uuid FROM admins ORDER BY rowid")]

    def password_hash(self) -> bytes | None:
        return self._conn.execute("SELECT admin_password_hash FROM settings WHERE id = 1").fetchone()[0]

    def set_password_hash(self, password_hash: bytes | None) -> None:
        with self._conn:
            self._conn.execute("UPDATE settings SET admin_password_hash = ? WHERE id = 1", [password_hash])

    # --- Broadcast deliveries ---

    def save_deliveries(self, author: str, broadcast_ts: int, deliveries: Mapping[str, int]) -> None:
        """Records the timestamp of the copy of a broadcast that each recipient received.

        `broadcast_ts` is the timestamp of the author's message. Like Signal does, each edit targets the
        previous version of the message, so every version is stored under its own timestamp.
        """
        with self._conn:
            self._conn.executemany(
                "INSERT OR REPLACE INTO broadcast_deliveries "
                "(author, broadcast_ts, recipient, recipient_ts) VALUES (?, ?, ?, ?)",
                [(author, broadcast_ts, recipient, ts) for recipient, ts in deliveries.items()],
            )

    def deliveries(self, author: str, broadcast_ts: int) -> dict[str, int]:
        """The timestamp of the copy that each recipient received of a broadcast, empty if `author` sent
        no broadcast at `broadcast_ts` (e.g. it was a command or it has expired)."""
        rows = self._conn.execute(
            "SELECT recipient, recipient_ts FROM broadcast_deliveries WHERE author = ? AND broadcast_ts = ?",
            [author, broadcast_ts],
        )
        return dict(rows.fetchall())

    def broadcast_author(self, recipient: str, recipient_ts: int) -> str | None:
        """Who sent the broadcast that `recipient` received at `recipient_ts`."""
        row = self._conn.execute(
            "SELECT author FROM broadcast_deliveries WHERE recipient = ? AND recipient_ts = ?",
            [recipient, recipient_ts],
        ).fetchone()
        return row[0] if row is not None else None

    def delete_deliveries_before(self, cutoff_ts: int) -> int:
        """Deletes the deliveries of broadcasts sent before `cutoff_ts` (ms). Returns how many were deleted."""
        with self._conn:
            cursor = self._conn.execute("DELETE FROM broadcast_deliveries WHERE broadcast_ts < ?", [cutoff_ts])
        return cursor.rowcount

    # --- Messages to the admins ---

    def pseudonym_for(self, uuid: str, now_ts: int) -> int:
        """The number that identifies `uuid` to the admins. It stays the same while the user keeps
        writing and expires `delete_expired_admin_messages` after their last message."""
        with self._conn:
            row = self._conn.execute(
                "INSERT INTO pseudonyms (uuid, last_message_at) VALUES (?, ?) "
                "ON CONFLICT (uuid) DO UPDATE SET last_message_at = excluded.last_message_at RETURNING id",
                [uuid, now_ts],
            ).fetchone()
        return row[0]

    def save_admin_message(self, admin: str, recipient_ts: int, pseudonym_id: int, sent_at: int) -> None:
        """Records that the message `admin` received at `recipient_ts` is about the user `pseudonym_id`,
        so the admin can quote it to reply to them."""
        with self._conn:
            self._conn.execute(
                "INSERT OR REPLACE INTO admin_messages (admin, recipient_ts, pseudonym_id, sent_at) "
                "VALUES (?, ?, ?, ?)",
                [admin, recipient_ts, pseudonym_id, sent_at],
            )

    def admin_message_sender(self, admin: str, recipient_ts: int) -> ForwardedMessageSender | None:
        row = self._conn.execute(
            "SELECT pseudonyms.uuid, pseudonyms.id FROM admin_messages "
            "JOIN pseudonyms ON pseudonyms.id = admin_messages.pseudonym_id "
            "WHERE admin_messages.admin = ? AND admin_messages.recipient_ts = ?",
            [admin, recipient_ts],
        ).fetchone()
        return ForwardedMessageSender(*row) if row is not None else None

    def delete_expired_admin_messages(self, cutoff_ts: int) -> None:
        """Forgets the admin messages sent before `cutoff_ts` (ms) and the pseudonyms of users who have
        not written since. A pseudonym is never older than its newest message, so a message that can
        still be quoted always keeps its pseudonym."""
        with self._conn:
            self._conn.execute("DELETE FROM admin_messages WHERE sent_at < ?", [cutoff_ts])
            self._conn.execute("DELETE FROM pseudonyms WHERE last_message_at < ?", [cutoff_ts])

    def _exists(self, query: str, *params: object) -> bool:
        return self._conn.execute(query, params).fetchone() is not None

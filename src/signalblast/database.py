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
class ConversationMessage:
    """A message between a user and the admins. Every chat that it reached has a copy of it."""

    id: int
    # The user the conversation is with
    user: str
    # False if an admin wrote it
    from_user: bool


@dataclass(frozen=True)
class MessageCopy:
    """The copy of a conversation message in someone's chat with the bot, enough to quote it."""

    timestamp: int
    # None if the bot sent it
    author: str | None


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

    def add_conversation_message(self, user: str, *, from_user: bool, sent_at: int) -> int:
        """Records a message in the conversation between `user` and the admins, written by `user` or by an
        admin. Only who it belongs to is stored, not its content. Returns its id."""
        with self._conn:
            row = self._conn.execute(
                "INSERT INTO conversation_messages (user, from_user, sent_at) VALUES (?, ?, ?) RETURNING id",
                [user, from_user, sent_at],
            ).fetchone()
        return row[0]

    def add_copy(self, message_id: int, chat: str, timestamp: int, author: str | None) -> None:
        """Records that the chat between `chat` and the bot has a copy of the message `message_id` at
        `timestamp`, written by `author` (None for the bot)."""
        with self._conn:
            self._conn.execute(
                "INSERT OR REPLACE INTO conversation_copies (message_id, chat, timestamp, author) VALUES (?, ?, ?, ?)",
                [message_id, chat, timestamp, author],
            )

    def conversation_message(self, chat: str, timestamp: int) -> ConversationMessage | None:
        """The conversation message that the copy at `timestamp` in the chat with `chat` belongs to."""
        row = self._conn.execute(
            "SELECT m.id, m.user, m.from_user FROM conversation_copies c "
            "JOIN conversation_messages m ON m.id = c.message_id WHERE c.chat = ? AND c.timestamp = ?",
            [chat, timestamp],
        ).fetchone()
        return ConversationMessage(row[0], row[1], bool(row[2])) if row is not None else None

    def copy_in_chat(self, message_id: int, chat: str) -> MessageCopy | None:
        """The first copy of the message `message_id` in the chat with `chat`, i.e. the sender's own message
        in their chat."""
        row = self._conn.execute(
            "SELECT timestamp, author FROM conversation_copies WHERE message_id = ? AND chat = ? "
            "ORDER BY rowid LIMIT 1",
            [message_id, chat],
        ).fetchone()
        return MessageCopy(*row) if row is not None else None

    def delete_expired_conversations(self, cutoff_ts: int) -> None:
        """Forgets the conversation messages sent before `cutoff_ts` (ms), and their copies."""
        with self._conn:
            self._conn.execute("DELETE FROM conversation_messages WHERE sent_at < ?", [cutoff_ts])

    def _exists(self, query: str, *params: object) -> bool:
        return self._conn.execute(query, params).fetchone() is not None

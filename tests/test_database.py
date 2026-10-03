from __future__ import annotations

from typing import TYPE_CHECKING

from signalblast.database import ConversationMessage, Database, MessageCopy

if TYPE_CHECKING:
    from pathlib import Path

DAY_MS = 24 * 60 * 60 * 1000


def make_db() -> Database:
    return Database(":memory:")


def test_subscribers() -> None:
    db = make_db()

    assert db.add_subscriber("uuid-b")
    assert db.add_subscriber("uuid-a")
    assert not db.add_subscriber("uuid-a")

    assert db.is_subscriber("uuid-a")
    assert db.subscribers() == ["uuid-b", "uuid-a"]
    assert db.subscriber_count() == 2  # noqa: PLR2004

    assert db.remove_subscriber("uuid-a")
    assert not db.remove_subscriber("uuid-a")
    assert db.subscribers() == ["uuid-b"]


def test_failed_sends_count_until_a_send_succeeds() -> None:
    db = make_db()
    db.add_subscriber("uuid-1")

    assert db.record_send_failure("uuid-1") == 1
    assert db.record_send_failure("uuid-1") == 2  # noqa: PLR2004
    db.record_send_success("uuid-1")
    assert db.record_send_failure("uuid-1") == 1

    assert db.record_send_failure("not-subscribed") == 0


def test_ban_unsubscribes_and_numbers_are_never_reused() -> None:
    db = make_db()
    db.add_subscriber("uuid-1")

    first_id, is_new = db.ban("uuid-1", "spam spam")
    assert is_new
    assert db.is_banned("uuid-1")
    assert not db.is_subscriber("uuid-1")
    assert db.ban("uuid-1", "other") == (first_id, False)

    [ban] = db.bans()
    assert (ban.id, ban.uuid, ban.snippet) == (first_id, "uuid-1", "spam spam")

    assert db.lift_ban(first_id) == "uuid-1"
    assert db.lift_ban(first_id) is None
    assert not db.is_banned("uuid-1")

    second_id, _ = db.ban("uuid-2", None)
    assert second_id > first_id


def test_deleted_data_is_not_left_in_the_file(tmp_path: Path) -> None:
    path = tmp_path / "signalblast.db"
    db = Database(path)
    ban_id, _ = db.ban("uuid-secret", "a secret snippet")
    db.lift_ban(ban_id)
    db.close()

    content = path.read_bytes()
    assert b"uuid-secret" not in content
    assert b"a secret snippet" not in content


def test_admins_and_password() -> None:
    db = make_db()
    assert db.password_hash() is None

    db.set_password_hash(b"hash")
    assert db.password_hash() == b"hash"

    assert db.add_admin("admin-1")
    assert not db.add_admin("admin-1")
    assert db.add_admin("admin-2")
    assert db.is_admin("admin-1")
    assert db.admins() == ["admin-1", "admin-2"]
    assert db.remove_admin("admin-1")
    assert not db.remove_admin("admin-1")
    assert db.admins() == ["admin-2"]


def test_deliveries_of_edits() -> None:
    db = make_db()
    db.save_deliveries("author", 1000, {"author": 1001, "uuid-1": 1002})
    db.save_deliveries("someone-else", 1000, {"uuid-1": 1003})
    # The author's edit at 2000 reaches a late subscriber as a new message and the original recipients as edits
    db.save_deliveries("author", 2000, {"author": 2002, "uuid-1": 2003, "uuid-2": 2001})

    assert db.deliveries("author", 2000) == {"author": 2002, "uuid-1": 2003, "uuid-2": 2001}
    assert db.deliveries("author", 1000) == {"author": 1001, "uuid-1": 1002}
    assert db.deliveries("author", 999) == {}
    assert db.deliveries("someone-else", 1000) == {"uuid-1": 1003}

    # Quotes of both the first and the edited copies lead to the author
    assert db.broadcast_author("uuid-1", 1002) == "author"
    assert db.broadcast_author("uuid-1", 2003) == "author"
    assert db.broadcast_author("uuid-1", 1001) is None


def test_old_deliveries_are_deleted() -> None:
    db = make_db()
    db.save_deliveries("author", 1000, {"uuid-1": 1001})
    db.save_deliveries("author", 3000, {"uuid-1": 3001})

    assert db.delete_deliveries_before(2000) == 1
    assert db.deliveries("author", 1000) == {}
    assert db.deliveries("author", 3000) == {"uuid-1": 3001}


def test_conversations_expire_after_7_days() -> None:
    db = make_db()
    old = db.add_conversation_message("uuid-1", author="uuid-1", sent_at=0)
    db.add_copy(old, "uuid-1", 100)
    db.add_copy(old, "admin", 101)
    new = db.add_conversation_message("uuid-1", author="admin", sent_at=6 * DAY_MS)
    db.add_copy(new, "admin", 200)

    db.delete_expired_conversations(cutoff_ts=8 * DAY_MS - 7 * DAY_MS)

    assert db.conversation_message("uuid-1", 100) is None
    assert db.conversation_message("admin", 101) is None
    assert db.conversation_message("admin", 200) == ConversationMessage(new, "uuid-1", "admin")
    assert db.conversation_message("other-admin", 200) is None


def test_the_first_copy_in_a_chat_is_quoted() -> None:
    db = make_db()
    message_id = db.add_conversation_message("uuid-1", author="uuid-1", sent_at=0)
    db.add_copy(message_id, "uuid-1", 100)
    db.add_copy(message_id, "uuid-1", 101)
    db.add_copy(message_id, "admin", 102)

    assert db.copy_in_chat(message_id, "uuid-1") == MessageCopy(100, "uuid-1")
    # The bot sent the admin's copy
    assert db.copy_in_chat(message_id, "admin") == MessageCopy(102, None)
    assert db.copy_in_chat(message_id, "other-admin") is None

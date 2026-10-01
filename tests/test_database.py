from __future__ import annotations

from signalblast.database import Database, ForwardedMessageSender

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
    db.save_deliveries("author", 1000, {"author": 1001, "uuid-1": 1002}, is_edit=False)
    # The edit reaches a late subscriber as a new message and the original recipients as edits
    db.save_deliveries("author", 1000, {"uuid-2": 2001}, is_edit=False)
    db.save_deliveries("author", 1000, {"author": 2002, "uuid-1": 2003}, is_edit=True)

    assert db.first_deliveries("author", 1000) == {"author": 1001, "uuid-1": 1002, "uuid-2": 2001}
    assert db.first_deliveries("author", 999) == {}
    assert db.first_deliveries("someone-else", 1000) == {}

    # Quotes of both the first and the edited copies lead to the author
    assert db.broadcast_author("uuid-1", 1002) == "author"
    assert db.broadcast_author("uuid-1", 2003) == "author"
    assert db.broadcast_author("uuid-1", 1001) is None


def test_old_deliveries_are_deleted() -> None:
    db = make_db()
    db.save_deliveries("author", 1000, {"uuid-1": 1001}, is_edit=False)
    db.save_deliveries("author", 3000, {"uuid-1": 3001}, is_edit=False)

    assert db.delete_deliveries_before(2000) == 1
    assert db.first_deliveries("author", 1000) == {}
    assert db.first_deliveries("author", 3000) == {"uuid-1": 3001}


def test_pseudonym_is_kept_while_the_user_keeps_writing() -> None:
    db = make_db()
    first = db.pseudonym_for("uuid-1", now_ts=0)
    other = db.pseudonym_for("uuid-2", now_ts=0)
    assert first != other

    # Writes every 5 days, the pseudonym is never more than 7 days without a message
    for day in (5, 10, 15):
        db.delete_expired_admin_messages(cutoff_ts=day * DAY_MS - 7 * DAY_MS)
        assert db.pseudonym_for("uuid-1", now_ts=day * DAY_MS) == first


def test_pseudonym_expires_after_7_days_without_messages() -> None:
    db = make_db()
    first = db.pseudonym_for("uuid-1", now_ts=0)
    db.save_admin_message("admin", recipient_ts=100, pseudonym_id=first, sent_at=0)
    assert db.admin_message_sender("admin", 100) == ForwardedMessageSender("uuid-1", first)

    now = 8 * DAY_MS
    db.delete_expired_admin_messages(cutoff_ts=now - 7 * DAY_MS)

    assert db.admin_message_sender("admin", 100) is None
    assert db.pseudonym_for("uuid-1", now_ts=now) > first


def test_purge_keeps_messages_that_can_still_be_quoted() -> None:
    db = make_db()
    pseudonym = db.pseudonym_for("uuid-1", now_ts=0)
    db.save_admin_message("admin", recipient_ts=100, pseudonym_id=pseudonym, sent_at=0)
    db.pseudonym_for("uuid-1", now_ts=6 * DAY_MS)
    db.save_admin_message("admin", recipient_ts=200, pseudonym_id=pseudonym, sent_at=6 * DAY_MS)

    db.delete_expired_admin_messages(cutoff_ts=8 * DAY_MS - 7 * DAY_MS)

    assert db.admin_message_sender("admin", 100) is None
    assert db.admin_message_sender("admin", 200) == ForwardedMessageSender("uuid-1", pseudonym)
    assert db.admin_message_sender("other-admin", 200) is None

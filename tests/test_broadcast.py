from __future__ import annotations

from typing import TYPE_CHECKING

from chat_support import (
    ATTACHMENT_CONTENT,
    OTHER_SUBSCRIBER,
    STRANGER,
    SUBSCRIBER,
    edit,
    message,
    remote_delete,
    timestamp_of,
)

from signalblast.commands import broadcast

if TYPE_CHECKING:
    import pytest
    from chat_support import Chat

THIRD_SUBSCRIBER = "66666666-6666-6666-6666-666666666666"


async def test_broadcast_reaches_every_subscriber(chat: Chat) -> None:
    await chat.start(subscribers=(SUBSCRIBER, OTHER_SUBSCRIBER, THIRD_SUBSCRIBER))

    await chat.send(message("Hello everyone", source=SUBSCRIBER))

    assert chat.texts_to(OTHER_SUBSCRIBER) == ["Hello everyone"]
    assert chat.texts_to(THIRD_SUBSCRIBER) == ["Hello everyone"]
    # The sender gets a copy too, then the confirmation, which doesn't count them
    assert chat.texts_to(SUBSCRIBER) == ["Hello everyone", "Message sent to 2 people"]


async def test_broadcast_command_and_attachments(chat: Chat) -> None:
    await chat.start(subscribers=(SUBSCRIBER, OTHER_SUBSCRIBER))

    await chat.send(message("!broadcast Look at this", source=SUBSCRIBER, attachment=True))
    await chat.send(message(None, source=SUBSCRIBER, attachment=True))

    copies = [s for s in chat.sent if s.recipient == OTHER_SUBSCRIBER]
    assert [(s.text, s.attachments) for s in copies] == [
        ("Look at this", [ATTACHMENT_CONTENT]),
        ("", [ATTACHMENT_CONTENT]),
    ]


async def test_nothing_to_broadcast(chat: Chat) -> None:
    await chat.start(subscribers=(SUBSCRIBER, OTHER_SUBSCRIBER))

    [reply] = await chat.send(message("!broadcast", source=SUBSCRIBER))

    assert reply.text == "There is nothing to broadcast, write your message after !broadcast"


async def test_banned_users_cannot_broadcast(chat: Chat) -> None:
    await chat.start(subscribers=(OTHER_SUBSCRIBER,))
    chat.bot.db.ban(SUBSCRIBER, None)

    [reply] = await chat.send(message("Hello", source=SUBSCRIBER))

    assert reply.text == "This number is not allowed to send messages"


async def test_only_subscribers_can_broadcast(chat: Chat) -> None:
    await chat.start(subscribers=(SUBSCRIBER,))

    [reply] = await chat.send(message("Hello", source=STRANGER))

    assert str(reply.text).startswith("To be able to send messages you must sign up.")
    assert chat.texts_to(SUBSCRIBER) == []


async def test_edit_reaches_every_copy_and_new_subscribers(chat: Chat) -> None:
    await chat.start(subscribers=(SUBSCRIBER, OTHER_SUBSCRIBER))
    original = message("Helo", source=SUBSCRIBER)
    await chat.send(original)
    first_copy = chat.last_to(OTHER_SUBSCRIBER)
    chat.bot.db.add_subscriber(THIRD_SUBSCRIBER)

    first_edit = edit("Hello", source=SUBSCRIBER, target_timestamp=timestamp_of(original))
    await chat.send(first_edit)

    edited = chat.last_to(OTHER_SUBSCRIBER)
    assert (edited.text, edited.edit_timestamp) == ("Hello", first_copy.timestamp)
    late = chat.last_to(THIRD_SUBSCRIBER)
    assert (late.text, late.edit_timestamp) == ("Hello", None)
    assert chat.texts_to(SUBSCRIBER)[-1] == "Message edited for 2 people"

    # Signal targets the second edit at the first one, it edits the late subscriber's copy as well. Like
    # Signal, each copy edits the previous one
    second_edit = edit("Hello!", source=SUBSCRIBER, target_timestamp=timestamp_of(first_edit))
    await chat.send(second_edit)
    assert chat.last_to(OTHER_SUBSCRIBER).edit_timestamp == edited.timestamp
    assert chat.last_to(THIRD_SUBSCRIBER).edit_timestamp == late.timestamp

    # Deleting the edited message deletes the latest copies
    latest = {(s.recipient, s.timestamp) for s in chat.sent if s.text == "Hello!"}
    await chat.send(remote_delete(source=SUBSCRIBER, target_timestamp=timestamp_of(second_edit)))
    assert set(chat.deleted) == latest


async def test_delete_removes_every_copy(chat: Chat) -> None:
    await chat.start(subscribers=(SUBSCRIBER, OTHER_SUBSCRIBER))
    original = message("Oops", source=SUBSCRIBER)
    sent = await chat.send(original)
    copies = {(s.recipient, s.timestamp) for s in sent if s.text == "Oops"}

    await chat.send(remote_delete(source=SUBSCRIBER, target_timestamp=timestamp_of(original)))

    assert set(chat.deleted) == copies
    assert chat.texts_to(SUBSCRIBER)[-1] == "Message deleted for 1 person"


FOLLOW_UP = "Is the bot still working?"


async def test_edit_of_a_non_broadcast_is_sent_as_a_new_broadcast(chat: Chat) -> None:
    # Regression: this used to leave a lock acquired, freezing the bot on the next broadcast
    await chat.start(subscribers=(SUBSCRIBER, OTHER_SUBSCRIBER))

    first_edit = edit("Hello", source=SUBSCRIBER, target_timestamp=1_000)
    await chat.send(first_edit)
    await chat.send(message(FOLLOW_UP, source=SUBSCRIBER))

    assert chat.texts_to(OTHER_SUBSCRIBER) == ["Hello", FOLLOW_UP]
    assert all(s.edit_timestamp is None for s in chat.sent)

    # Editing the same message again edits that broadcast instead of sending another one
    first_copy = next(s for s in chat.sent if s.recipient == OTHER_SUBSCRIBER)
    await chat.send(edit("Hello!", source=SUBSCRIBER, target_timestamp=timestamp_of(first_edit)))
    assert chat.last_to(OTHER_SUBSCRIBER).edit_timestamp == first_copy.timestamp


async def test_delete_of_a_non_broadcast_is_ignored(chat: Chat) -> None:
    await chat.start(subscribers=(SUBSCRIBER, OTHER_SUBSCRIBER))

    assert await chat.send(remote_delete(source=SUBSCRIBER, target_timestamp=1_000)) == []
    await chat.send(message(FOLLOW_UP, source=SUBSCRIBER))

    assert chat.deleted == []
    assert chat.texts_to(OTHER_SUBSCRIBER) == [FOLLOW_UP]


async def test_failed_sends_are_retried_then_reported(chat: Chat) -> None:
    await chat.start(subscribers=(SUBSCRIBER, OTHER_SUBSCRIBER, THIRD_SUBSCRIBER))
    chat.unreachable.add(THIRD_SUBSCRIBER)

    await chat.send(message("Hello", source=SUBSCRIBER))
    reply = chat.last_to(SUBSCRIBER)
    assert reply.text == "Message sent to 1 out of 2 people, trying the rest again in a few minutes"

    await chat.run_retries()

    edited = chat.last_to(SUBSCRIBER)
    assert (edited.text, edited.edit_timestamp, edited.quote_timestamp) == (
        "Message sent to 1 out of 2 people, please contact the admins with !admin if this keeps happening",
        reply.timestamp,
        reply.quote_timestamp,
    )
    assert chat.bot.broadcast_retries == {}


async def test_retry_reaches_subscribers_back_online(chat: Chat) -> None:
    await chat.start(subscribers=(SUBSCRIBER, OTHER_SUBSCRIBER, THIRD_SUBSCRIBER))
    chat.unreachable.add(THIRD_SUBSCRIBER)
    original = message("Hello", source=SUBSCRIBER)
    await chat.send(original)
    reply = chat.last_to(SUBSCRIBER)
    chat.unreachable.clear()

    await chat.run_retries()

    assert chat.texts_to(THIRD_SUBSCRIBER) == ["Hello"]
    edited = chat.last_to(SUBSCRIBER)
    assert (edited.text, edited.edit_timestamp) == ("Message sent to 2 people", reply.timestamp)
    # The copy sent by the retry is edited like the others
    late_copy = chat.last_to(THIRD_SUBSCRIBER)
    await chat.send(edit("Hello!", source=SUBSCRIBER, target_timestamp=timestamp_of(original)))
    assert chat.last_to(THIRD_SUBSCRIBER).edit_timestamp == late_copy.timestamp


async def test_nothing_is_retried_when_every_send_works(chat: Chat) -> None:
    await chat.start(subscribers=(SUBSCRIBER, OTHER_SUBSCRIBER))

    await chat.send(message("Hello", source=SUBSCRIBER))

    assert chat.bot.broadcast_retries == {}


async def test_edit_cancels_the_pending_retry(chat: Chat) -> None:
    await chat.start(subscribers=(SUBSCRIBER, OTHER_SUBSCRIBER, THIRD_SUBSCRIBER))
    chat.unreachable.add(THIRD_SUBSCRIBER)
    original = message("Helo", source=SUBSCRIBER)
    await chat.send(original)
    chat.unreachable.clear()

    await chat.send(edit("Hello", source=SUBSCRIBER, target_timestamp=timestamp_of(original)))
    await chat.run_retries()

    # The subscriber who missed the original gets the edit as a new message, and nothing else
    assert chat.texts_to(THIRD_SUBSCRIBER) == ["Hello"]
    assert chat.last_to(THIRD_SUBSCRIBER).edit_timestamp is None
    assert chat.texts_to(SUBSCRIBER)[-1] == "Message edited for 2 people"


async def test_delete_cancels_the_pending_retry(chat: Chat) -> None:
    await chat.start(subscribers=(SUBSCRIBER, OTHER_SUBSCRIBER, THIRD_SUBSCRIBER))
    chat.unreachable.add(THIRD_SUBSCRIBER)
    original = message("Oops", source=SUBSCRIBER)
    await chat.send(original)
    chat.unreachable.clear()

    await chat.send(remote_delete(source=SUBSCRIBER, target_timestamp=timestamp_of(original)))
    await chat.run_retries()

    assert chat.texts_to(THIRD_SUBSCRIBER) == []
    assert chat.texts_to(SUBSCRIBER)[-1] == "Message deleted for 1 person"


async def test_failed_deletes_are_retried(chat: Chat) -> None:
    await chat.start(subscribers=(SUBSCRIBER, OTHER_SUBSCRIBER, THIRD_SUBSCRIBER))
    original = message("Oops", source=SUBSCRIBER)
    await chat.send(original)
    chat.unreachable.add(THIRD_SUBSCRIBER)

    await chat.send(remote_delete(source=SUBSCRIBER, target_timestamp=timestamp_of(original)))
    reply = chat.last_to(SUBSCRIBER)
    assert reply.text == "Message deleted for 1 out of 2 people, trying the rest again in a few minutes"

    chat.unreachable.clear()
    await chat.run_retries()

    assert {recipient for recipient, _ in chat.deleted} == {SUBSCRIBER, OTHER_SUBSCRIBER, THIRD_SUBSCRIBER}
    edited = chat.last_to(SUBSCRIBER)
    assert (edited.text, edited.edit_timestamp) == ("Message deleted for 2 people", reply.timestamp)


async def test_retry_does_not_show_the_typing_indicator(chat: Chat) -> None:
    await chat.start(subscribers=(SUBSCRIBER, OTHER_SUBSCRIBER))
    # The sender's own copy fails
    chat.unreachable.add(SUBSCRIBER)
    await chat.send(message("Hello", source=SUBSCRIBER))
    chat.unreachable.clear()
    num_typing = chat.start_typing.await_count

    await chat.run_retries()

    assert chat.texts_to(SUBSCRIBER) == ["Hello"]
    assert chat.start_typing.await_count == num_typing


async def test_unreachable_subscribers_are_removed(chat: Chat) -> None:
    await chat.start(subscribers=(SUBSCRIBER, OTHER_SUBSCRIBER))
    chat.unreachable.add(OTHER_SUBSCRIBER)

    for i in range(broadcast.MAX_FAILED_SENDS - 1):
        await chat.send(message(f"Hello {i}", source=SUBSCRIBER))
        await chat.run_retries()
        assert chat.bot.db.is_subscriber(OTHER_SUBSCRIBER)

    await chat.send(message("Hello again", source=SUBSCRIBER))
    # Only the failed retry counts
    assert chat.bot.db.is_subscriber(OTHER_SUBSCRIBER)
    await chat.run_retries()
    assert not chat.bot.db.is_subscriber(OTHER_SUBSCRIBER)


async def test_failure_count_resets_after_a_successful_send(chat: Chat) -> None:
    await chat.start(subscribers=(SUBSCRIBER, OTHER_SUBSCRIBER))
    chat.unreachable.add(OTHER_SUBSCRIBER)
    for i in range(broadcast.MAX_FAILED_SENDS - 1):
        await chat.send(message(f"Hello {i}", source=SUBSCRIBER))
        await chat.run_retries()

    # Back online by the time of the retry
    await chat.send(message("Back online", source=SUBSCRIBER))
    chat.unreachable.clear()
    await chat.run_retries()
    chat.unreachable.add(OTHER_SUBSCRIBER)
    await chat.send(message("Down again", source=SUBSCRIBER))
    await chat.run_retries()

    assert chat.bot.db.is_subscriber(OTHER_SUBSCRIBER)


def typing_jobs(chat: Chat) -> list[object]:
    return [job for job in chat.bot.scheduler.get_jobs() if job.name.endswith("start_typing")]


async def test_typing_indicator_stops_when_the_broadcast_fails(chat: Chat, monkeypatch: pytest.MonkeyPatch) -> None:
    await chat.start(subscribers=(SUBSCRIBER, OTHER_SUBSCRIBER))

    async def fail(*_args: object) -> None:
        raise RuntimeError

    monkeypatch.setattr(broadcast, "_send_to_each", fail)
    [reply] = await chat.send(message("Hello", source=SUBSCRIBER))

    assert reply.text == "Something went wrong, please try again"
    assert typing_jobs(chat) == []
    assert chat.stop_typing.await_count == 1

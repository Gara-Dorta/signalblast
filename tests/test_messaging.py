from __future__ import annotations

from typing import TYPE_CHECKING

from chat_support import (
    ADMIN,
    ATTACHMENT_CONTENT,
    BOT,
    OTHER_ADMIN,
    OTHER_SUBSCRIBER,
    SUBSCRIBER,
    message,
    timestamp_of,
)

if TYPE_CHECKING:
    from chat_support import Chat, Sent


async def forward(chat: Chat, text: str, *, source: str = SUBSCRIBER, to: str = ADMIN) -> Sent:
    """`source` sends `text` with !admin, returns the copy that the admin `to` received."""
    sent = await chat.send(message(f"!admin {text}", source=source))
    [forwarded] = [s for s in sent if s.recipient == to]
    return forwarded


async def test_messages_reach_every_admin_without_the_senders_id(chat: Chat) -> None:
    await chat.start(subscribers=(SUBSCRIBER, OTHER_SUBSCRIBER), admins=(ADMIN, OTHER_ADMIN))

    sent = await chat.send(message("!admin Please help", source=SUBSCRIBER, attachment=True))

    assert {(s.recipient, s.text) for s in sent} == {
        (ADMIN, "User wrote:\nPlease help"),
        (OTHER_ADMIN, "User wrote:\nPlease help"),
        (SUBSCRIBER, "Message sent to the admins"),
    }
    assert all(s.attachments == [ATTACHMENT_CONTENT] for s in sent if s.recipient != SUBSCRIBER)
    assert chat.texts_to(OTHER_SUBSCRIBER) == []


async def test_replies_reach_the_sender_of_the_quoted_message(chat: Chat) -> None:
    await chat.start(admins=(ADMIN,))
    first = await forward(chat, "first", source=SUBSCRIBER)
    other = await forward(chat, "hello", source=OTHER_SUBSCRIBER)

    await chat.send(message("To first", source=ADMIN, quote=first))
    await chat.send(message("To other", source=ADMIN, quote=other))

    assert chat.texts_to(SUBSCRIBER)[-1] == "Admin: To first"
    assert chat.texts_to(OTHER_SUBSCRIBER)[-1] == "Admin: To other"


async def test_admin_replies_by_quoting(chat: Chat) -> None:
    await chat.start(subscribers=(SUBSCRIBER, OTHER_SUBSCRIBER, ADMIN), admins=(ADMIN, OTHER_ADMIN))
    question = message("!admin Please help", source=SUBSCRIBER)
    first = await chat.send(question)
    forwarded = {s.recipient: s for s in first}

    reply = message("Sure, what's up?", source=ADMIN, quote=forwarded[ADMIN])
    sent = await chat.send(reply)

    # Each copy quotes, in its own chat, the copy of the message it answers
    assert {(s.recipient, s.text, s.quote_timestamp, s.quote_author) for s in sent} == {
        (SUBSCRIBER, "Admin: Sure, what's up?", timestamp_of(question), SUBSCRIBER),
        (ADMIN, "Reply sent to user", timestamp_of(reply), ADMIN),
        (OTHER_ADMIN, "User was answered by an admin:\nSure, what's up?", forwarded[OTHER_ADMIN].timestamp, BOT),
    }
    # The reply is private, not broadcast
    assert chat.texts_to(OTHER_SUBSCRIBER) == []


async def test_user_answers_by_quoting_the_admin_reply(chat: Chat) -> None:
    await chat.start(subscribers=(SUBSCRIBER, OTHER_SUBSCRIBER, ADMIN), admins=(ADMIN, OTHER_ADMIN))
    forwarded = await forward(chat, "Please help")
    reply = message("Sure, what's up?", source=ADMIN, quote=forwarded)
    await chat.send(reply)
    admin_reply = chat.last_to(SUBSCRIBER)
    answered = chat.last_to(OTHER_ADMIN)

    answer = message("My app crashes", source=SUBSCRIBER, quote=admin_reply, attachment=True)
    sent = await chat.send(answer)

    assert {(s.recipient, s.text, s.quote_timestamp, s.quote_author) for s in sent} == {
        (ADMIN, "User replied:\nMy app crashes", timestamp_of(reply), ADMIN),
        (OTHER_ADMIN, "User replied:\nMy app crashes", answered.timestamp, BOT),
        (SUBSCRIBER, "Message sent to the admins", timestamp_of(answer), SUBSCRIBER),
    }
    assert all(s.attachments == [ATTACHMENT_CONTENT] for s in sent if s.recipient != SUBSCRIBER)
    # The answer is private, not broadcast
    assert chat.texts_to(OTHER_SUBSCRIBER) == []

    # And the conversation goes on by quoting
    [to_admin] = [s for s in sent if s.recipient == ADMIN]
    await chat.send(message("Update the app", source=ADMIN, quote=to_admin))
    assert chat.texts_to(SUBSCRIBER)[-1] == "Admin: Update the app"
    assert chat.last_to(SUBSCRIBER).quote_timestamp == timestamp_of(answer)


async def test_users_add_to_their_message_by_quoting_it(chat: Chat) -> None:
    await chat.start(subscribers=(SUBSCRIBER, OTHER_SUBSCRIBER), admins=(ADMIN,))
    question = message("!admin Please help", source=SUBSCRIBER)
    [forwarded] = [s for s in await chat.send(question) if s.recipient == ADMIN]

    await chat.send(message("It's urgent", source=SUBSCRIBER, quote=question))

    added = chat.last_to(ADMIN)
    assert (added.text, added.quote_timestamp) == ("User replied:\nIt's urgent", forwarded.timestamp)
    assert chat.texts_to(OTHER_SUBSCRIBER) == []


async def test_new_conversations_quote_nothing(chat: Chat) -> None:
    await chat.start(admins=(ADMIN,))

    forwarded = await forward(chat, "Please help")

    assert forwarded.quote_timestamp is None


async def test_banned_users_cannot_answer_the_admins(chat: Chat) -> None:
    await chat.start(subscribers=(SUBSCRIBER, OTHER_SUBSCRIBER), admins=(ADMIN,))
    forwarded = await forward(chat, "Please help")
    await chat.send(message("Sure", source=ADMIN, quote=forwarded))
    admin_reply = chat.last_to(SUBSCRIBER)
    await chat.send(message("!ban", source=ADMIN, quote=forwarded))

    [reply] = await chat.send(message("Why?", source=SUBSCRIBER, quote=admin_reply))

    assert (reply.recipient, reply.text) == (SUBSCRIBER, "You are not allowed to contact the admins")
    assert chat.texts_to(OTHER_SUBSCRIBER) == []


async def test_any_message_about_the_user_can_be_quoted(chat: Chat) -> None:
    await chat.start(admins=(ADMIN, OTHER_ADMIN))
    forwarded = await forward(chat, "Please help", to=OTHER_ADMIN)
    await chat.send(message("On it", source=OTHER_ADMIN, quote=forwarded))
    answered = chat.last_to(ADMIN)
    confirmation = chat.last_to(OTHER_ADMIN)

    await chat.send(message("Me too", source=ADMIN, quote=answered))
    await chat.send(message("One more thing", source=OTHER_ADMIN, quote=confirmation))

    assert chat.texts_to(SUBSCRIBER)[-2:] == ["Admin: Me too", "Admin: One more thing"]


async def test_replies_that_look_like_commands_still_reach_the_user(chat: Chat) -> None:
    await chat.start(admins=(ADMIN,))
    forwarded = await forward(chat, "Please help")

    await chat.send(message("!important: read the instructions", source=ADMIN, quote=forwarded))

    assert chat.texts_to(SUBSCRIBER)[-1] == "Admin: !important: read the instructions"


async def test_replies_to_expired_messages_are_not_sent_anywhere(chat: Chat) -> None:
    await chat.start(subscribers=(SUBSCRIBER, OTHER_SUBSCRIBER, ADMIN), admins=(ADMIN,))
    forwarded = await forward(chat, "Please help")
    confirmation = chat.last_to(SUBSCRIBER)
    await chat.send(message("Sure", source=ADMIN, quote=forwarded))
    admin_reply = chat.last_to(SUBSCRIBER)
    chat.bot.db.delete_expired_conversations(forwarded.timestamp * 10)

    [reply] = await chat.send(message("Sure", source=ADMIN, quote=forwarded))
    assert (reply.recipient, reply.text) == (
        ADMIN,
        "Not sent: this message is older than 7 days, so its sender can no longer be reached",
    )

    expired = "Not sent: this conversation is older than 7 days, write to the admins with !admin instead"
    [reply] = await chat.send(message("Thanks", source=SUBSCRIBER, quote=admin_reply))
    assert (reply.recipient, reply.text) == (SUBSCRIBER, expired)
    [reply] = await chat.send(message("Hello?", source=SUBSCRIBER, quote=confirmation))
    assert (reply.recipient, reply.text) == (SUBSCRIBER, expired)
    assert chat.texts_to(OTHER_SUBSCRIBER) == []


async def test_admins_are_told_when_the_reply_is_not_sent(chat: Chat) -> None:
    await chat.start(admins=(ADMIN, OTHER_ADMIN))
    forwarded = await forward(chat, "Please help")
    chat.unreachable.add(SUBSCRIBER)

    reply = message("Sure", source=ADMIN, quote=forwarded)
    [notice] = await chat.send(reply)

    assert (notice.recipient, notice.text, notice.quote_timestamp) == (
        ADMIN,
        "Reply not sent to user, please try again",
        timestamp_of(reply),
    )


async def test_former_admins_cannot_reply(chat: Chat) -> None:
    await chat.start(subscribers=(SUBSCRIBER, OTHER_SUBSCRIBER, ADMIN), admins=(ADMIN,))
    forwarded = await forward(chat, "Please help")
    chat.bot.db.remove_admin(ADMIN)

    [reply] = await chat.send(message("Sure", source=ADMIN, quote=forwarded))

    assert (reply.recipient, reply.text) == (ADMIN, "Not sent: only admins can reply to messages from users")


async def test_ban_the_sender_of_a_message_to_the_admins(chat: Chat) -> None:
    await chat.start(admins=(ADMIN,))
    forwarded = await forward(chat, "You are all idiots")

    await chat.send(message("!ban", source=ADMIN, quote=forwarded))

    assert chat.bot.db.is_banned(SUBSCRIBER)
    assert chat.texts_to(ADMIN)[-1] == 'Banned the sender of "You are all idiots" (ban #1), undo it with !lift ban 1'
    [reply] = await chat.send(message("!admin let me back", source=SUBSCRIBER))
    assert reply.text == "You are not allowed to contact the admins"


async def test_admin_replies_are_not_ban_targets(chat: Chat) -> None:
    await chat.start(admins=(ADMIN, OTHER_ADMIN))
    forwarded = await forward(chat, "Please help")
    await chat.send(message("Sure", source=ADMIN, quote=forwarded))

    await chat.send(message("!ban", source=OTHER_ADMIN, quote=chat.last_to(OTHER_ADMIN)))

    assert not chat.bot.db.is_banned(SUBSCRIBER)


async def test_no_admins(chat: Chat) -> None:
    await chat.start()

    [reply] = await chat.send(message("!admin hello?", source=SUBSCRIBER))

    assert reply.text == "I'm sorry but there are no admins to contact"


async def test_empty_message(chat: Chat) -> None:
    await chat.start(admins=(ADMIN,))

    [reply] = await chat.send(message("!admin", source=SUBSCRIBER))

    assert reply.text == "Write your message after !admin, e.g. !admin I have a question"


async def test_unreachable_admins(chat: Chat) -> None:
    await chat.start(admins=(ADMIN,))
    chat.unreachable.add(ADMIN)

    [reply] = await chat.send(message("!admin hello?", source=SUBSCRIBER))

    assert reply.text == "I couldn't reach the admins, please try again later"

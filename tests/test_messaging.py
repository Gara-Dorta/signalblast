from __future__ import annotations

from typing import TYPE_CHECKING

from chat_support import ADMIN, ATTACHMENT_CONTENT, OTHER_ADMIN, OTHER_SUBSCRIBER, SUBSCRIBER, message

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
        (ADMIN, "User #1 wrote:\nPlease help"),
        (OTHER_ADMIN, "User #1 wrote:\nPlease help"),
        (SUBSCRIBER, "Message sent to the admins"),
    }
    assert all(s.attachments == [ATTACHMENT_CONTENT] for s in sent if s.recipient != SUBSCRIBER)
    assert chat.texts_to(OTHER_SUBSCRIBER) == []


async def test_the_same_user_keeps_their_number(chat: Chat) -> None:
    await chat.start(admins=(ADMIN,))

    first = await forward(chat, "first", source=SUBSCRIBER)
    other = await forward(chat, "hello", source=OTHER_SUBSCRIBER)
    second = await forward(chat, "second", source=SUBSCRIBER)

    assert first.text == "User #1 wrote:\nfirst"
    assert other.text == "User #2 wrote:\nhello"
    assert second.text == "User #1 wrote:\nsecond"


async def test_admin_replies_by_quoting(chat: Chat) -> None:
    await chat.start(subscribers=(SUBSCRIBER, OTHER_SUBSCRIBER, ADMIN), admins=(ADMIN, OTHER_ADMIN))
    forwarded = await forward(chat, "Please help")

    sent = await chat.send(message("Sure, what's up?", source=ADMIN, quote=forwarded))

    assert {(s.recipient, s.text) for s in sent} == {
        (SUBSCRIBER, "Admin: Sure, what's up?"),
        (ADMIN, "User #1 received your reply"),
        (OTHER_ADMIN, "User #1 was answered by an admin:\nSure, what's up?"),
    }
    # The reply is private, not broadcast
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
    chat.bot.db.delete_expired_admin_messages(forwarded.timestamp * 10)

    [reply] = await chat.send(message("Sure", source=ADMIN, quote=forwarded))

    assert (reply.recipient, reply.text) == (
        ADMIN,
        "Not sent: this message is older than 7 days, so its sender can no longer be reached",
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

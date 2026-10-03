from __future__ import annotations

from typing import TYPE_CHECKING

from chat_support import ADMIN, OTHER_ADMIN, OTHER_SUBSCRIBER, SUBSCRIBER, message

if TYPE_CHECKING:
    from chat_support import Chat, Sent

ABUSE = "Some abusive message that goes on and on and on"
ABUSE_SNIPPET = "Some abusive message that goes on and on…"


async def received_broadcast(chat: Chat, text: str, *, author: str, recipient: str) -> Sent:
    """Broadcasts `text` and returns the copy that `recipient` received."""
    sent = await chat.send(message(text, source=author))
    [copy] = [s for s in sent if s.recipient == recipient and s.text == text]
    return copy


async def test_ban_the_sender_of_a_quoted_broadcast(chat: Chat) -> None:
    await chat.start(subscribers=(SUBSCRIBER, OTHER_SUBSCRIBER, ADMIN), admins=(ADMIN, OTHER_ADMIN))
    copy = await received_broadcast(chat, ABUSE, author=SUBSCRIBER, recipient=ADMIN)

    sent = await chat.send(message("!ban", source=ADMIN, quote=copy))

    assert chat.bot.db.is_banned(SUBSCRIBER)
    assert not chat.bot.db.is_subscriber(SUBSCRIBER)
    assert {(s.recipient, s.text) for s in sent} == {
        (SUBSCRIBER, "You have been banned"),
        (ADMIN, f'Banned the sender of "{ABUSE_SNIPPET}" (ban #1), undo it with !lift ban 1'),
        (OTHER_ADMIN, f'An admin banned the sender of "{ABUSE_SNIPPET}" (ban #1)'),
    }
    # Nobody learns who was banned
    assert all(SUBSCRIBER not in str(s.text) for s in sent)

    [reply] = await chat.send(message("!ban", source=ADMIN, quote=copy))
    assert reply.text == "Already banned (ban #1)"


async def test_ban_needs_a_quote_of_a_known_message(chat: Chat) -> None:
    await chat.start(subscribers=(ADMIN,), admins=(ADMIN,))
    [help_reply, _admin_help] = await chat.send(message("!help", source=ADMIN))

    for quote in (None, help_reply):
        [reply] = await chat.send(message("!ban", source=ADMIN, quote=quote))
        assert str(reply.text).startswith("To ban someone, quote their broadcast")


async def test_ban_after_the_broadcast_expired(chat: Chat) -> None:
    await chat.start(subscribers=(SUBSCRIBER, ADMIN), admins=(ADMIN,))
    copy = await received_broadcast(chat, ABUSE, author=SUBSCRIBER, recipient=ADMIN)
    chat.bot.db.delete_deliveries_before(copy.timestamp + 1)

    [reply] = await chat.send(message("!ban", source=ADMIN, quote=copy))

    assert str(reply.text).startswith("To ban someone, quote their broadcast")
    assert not chat.bot.db.is_banned(SUBSCRIBER)


async def test_admins_cannot_be_banned(chat: Chat) -> None:
    await chat.start(subscribers=(ADMIN, OTHER_ADMIN), admins=(ADMIN, OTHER_ADMIN))
    copy = await received_broadcast(chat, "hi", author=OTHER_ADMIN, recipient=ADMIN)

    [reply] = await chat.send(message("!ban", source=ADMIN, quote=copy))

    assert reply.text == "Admins can't be banned, remove them as admin first"


async def test_list_and_lift_bans(chat: Chat) -> None:
    await chat.start(admins=(ADMIN,))
    chat.bot.db.ban(SUBSCRIBER, "spam")
    chat.bot.db.ban(OTHER_SUBSCRIBER, None)

    [reply] = await chat.send(message("!list bans", source=ADMIN))
    [first, second] = str(reply.text).splitlines()[1:]
    assert first.startswith("#1 · ")
    assert first.endswith(' · "spam"')
    assert second.startswith("#2 · ")

    [notice, reply] = await chat.send(message("!lift ban #1", source=ADMIN))
    assert (notice.recipient, notice.text) == (
        SUBSCRIBER,
        "Your ban has been lifted, you can subscribe again with !subscribe",
    )
    assert reply.text == "Lifted ban #1"
    assert not chat.bot.db.is_banned(SUBSCRIBER)

    [reply] = await chat.send(message("!lift ban 1", source=ADMIN))
    assert reply.text == "There is no ban #1, see the ban numbers with !list bans"

    [reply] = await chat.send(message("!lift ban someone", source=ADMIN))
    assert reply.text == "Usage: !lift ban <number>, see the ban numbers with !list bans"


async def test_no_bans(chat: Chat) -> None:
    await chat.start(admins=(ADMIN,))

    [reply] = await chat.send(message("!list bans", source=ADMIN))

    assert reply.text == "Nobody is banned"


async def test_lifting_a_ban_reports_when_the_user_cannot_be_notified(chat: Chat) -> None:
    await chat.start(admins=(ADMIN,))
    chat.bot.db.ban(SUBSCRIBER, None)
    chat.unreachable.add(SUBSCRIBER)

    [reply] = await chat.send(message("!lift ban 1", source=ADMIN))

    assert reply.text == "Lifted ban #1. They could not be notified"

from __future__ import annotations

from typing import TYPE_CHECKING

from chat_support import SUBSCRIBER, message

if TYPE_CHECKING:
    from chat_support import Chat


async def test_subscribe(chat: Chat) -> None:
    await chat.start()

    [reply] = await chat.send(message("!subscribe", source=SUBSCRIBER))
    assert str(reply.text).startswith("Welcome! Any message that you send will be forwarded to everybody in the list.")
    assert "!unsubscribe" in str(reply.text)
    assert chat.bot.db.is_subscriber(SUBSCRIBER)

    [reply] = await chat.send(message("!subscribe", source=SUBSCRIBER))
    assert reply.text == "Already subscribed!"


async def test_subscribe_sets_disappearing_messages_after_the_welcome(chat: Chat) -> None:
    await chat.start(expiration_time=3600)
    num_sent_when_set: list[int] = []
    chat.update_contact.side_effect = lambda *_: num_sent_when_set.append(len(chat.sent))

    await chat.send(message("!subscribe", source=SUBSCRIBER))

    [call] = chat.update_contact.await_args_list
    assert call.args[0].expiration_in_seconds == 3600  # noqa: PLR2004
    assert num_sent_when_set == [1]


async def test_disappearing_messages_can_be_disabled(chat: Chat) -> None:
    await chat.start(expiration_time=0)

    await chat.send(message("!subscribe", source=SUBSCRIBER))

    assert chat.update_contact.await_count == 0


async def test_banned_users_cannot_subscribe(chat: Chat) -> None:
    await chat.start()
    chat.bot.db.ban(SUBSCRIBER, None)

    [reply] = await chat.send(message("!subscribe", source=SUBSCRIBER))

    assert reply.text == "This number is not allowed to subscribe"
    assert not chat.bot.db.is_subscriber(SUBSCRIBER)


async def test_unsubscribe(chat: Chat) -> None:
    await chat.start(subscribers=(SUBSCRIBER,))

    [reply] = await chat.send(message("!unsubscribe", source=SUBSCRIBER))
    assert reply.text == "Successfully unsubscribed!"
    assert not chat.bot.db.is_subscriber(SUBSCRIBER)

    [reply] = await chat.send(message("!unsubscribe", source=SUBSCRIBER))
    assert reply.text == "Not subscribed!"

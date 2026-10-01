from __future__ import annotations

from typing import TYPE_CHECKING

from chat_support import SUBSCRIBER, message

if TYPE_CHECKING:
    from chat_support import Chat


async def test_subscribe(chat: Chat) -> None:
    await chat.start(welcome_message="Welcome aboard!")

    [reply] = await chat.send(message("!subscribe", source=SUBSCRIBER))
    assert reply.text == "Welcome aboard!"
    assert chat.bot.db.is_subscriber(SUBSCRIBER)

    [reply] = await chat.send(message("!subscribe", source=SUBSCRIBER))
    assert reply.text == "Already subscribed!"


async def test_subscribe_sets_disappearing_messages(chat: Chat) -> None:
    await chat.start(expiration_time=3600)

    await chat.send(message("!subscribe", source=SUBSCRIBER))

    [call] = chat.update_contact.await_args_list
    assert call.args[0].expiration_in_seconds == 3600  # noqa: PLR2004


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

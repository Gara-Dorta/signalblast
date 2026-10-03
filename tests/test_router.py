from __future__ import annotations

from typing import TYPE_CHECKING

from chat_support import ADMIN, OTHER_SUBSCRIBER, STRANGER, SUBSCRIBER, message

if TYPE_CHECKING:
    from chat_support import Chat

UNDERSTOOD = "I'm happy to help!"
NOT_UNDERSTOOD = "I'm sorry, I didn't understand that."


async def test_unknown_commands_get_the_help_and_are_not_broadcast(chat: Chat) -> None:
    await chat.start(subscribers=(SUBSCRIBER, OTHER_SUBSCRIBER))

    for text in ("!subscibe", "!banana", "!list", "! broadcast hi"):
        [reply] = await chat.send(message(text, source=SUBSCRIBER))
        assert reply.recipient == SUBSCRIBER
        assert reply.text is not None
        assert reply.text.startswith(NOT_UNDERSTOOD)

    assert chat.texts_to(OTHER_SUBSCRIBER) == []


async def test_commands_are_case_insensitive(chat: Chat) -> None:
    await chat.start()

    await chat.send(message("!Subscribe", source=SUBSCRIBER))
    await chat.send(message("!HELP", source=SUBSCRIBER))

    assert chat.bot.db.is_subscriber(SUBSCRIBER)
    assert str(chat.last_to(SUBSCRIBER).text).startswith(UNDERSTOOD)


async def test_command_must_be_followed_by_a_space(chat: Chat) -> None:
    await chat.start()

    [reply] = await chat.send(message("!subscribeme", source=SUBSCRIBER))

    assert str(reply.text).startswith(NOT_UNDERSTOOD)
    assert not chat.bot.db.is_subscriber(SUBSCRIBER)


async def test_broadcast_command_allows_messages_starting_with_an_exclamation_mark(chat: Chat) -> None:
    await chat.start(subscribers=(SUBSCRIBER, OTHER_SUBSCRIBER))

    await chat.send(message("!broadcast !important news", source=SUBSCRIBER))

    assert chat.texts_to(OTHER_SUBSCRIBER) == ["!important news"]


async def test_command_words_inside_a_broadcast_are_kept(chat: Chat) -> None:
    await chat.start(subscribers=(SUBSCRIBER, OTHER_SUBSCRIBER))

    await chat.send(message("Send !broadcast to post", source=SUBSCRIBER))

    assert chat.texts_to(OTHER_SUBSCRIBER) == ["Send !broadcast to post"]


async def test_admin_only_commands(chat: Chat) -> None:
    await chat.start(admins=(ADMIN,))

    [reply, alert] = await chat.send(message("!list bans", source=STRANGER))

    assert (reply.recipient, reply.text) == (STRANGER, "I'm sorry but only admins can do that")
    assert alert.recipient == ADMIN
    assert alert.text == "Someone who is not an admin tried to use !list bans"


async def test_help_shows_the_admin_commands_only_to_admins(chat: Chat) -> None:
    await chat.start(admins=(ADMIN,), instructions_url="https://example.org/how-to")

    [user_help] = await chat.send(message("!help", source=STRANGER))
    [help_to_admin, admin_help] = await chat.send(message("!help", source=ADMIN))

    assert "!lift ban" not in str(user_help.text)
    assert "https://example.org/how-to" in str(user_help.text)
    assert help_to_admin.text == user_help.text
    assert str(admin_help.text).startswith("Admin commands:")
    assert "!lift ban <number>" in str(admin_help.text)


async def test_help_does_not_list_the_broadcast_command(chat: Chat) -> None:
    await chat.start()

    [reply] = await chat.send(message("!help", source=SUBSCRIBER))

    assert "!broadcast" not in str(reply.text)


async def test_group_messages_are_ignored(chat: Chat) -> None:
    await chat.start(subscribers=(SUBSCRIBER, OTHER_SUBSCRIBER))

    assert await chat.send(message("!help", source=SUBSCRIBER, group=True)) == []
    assert await chat.send(message("hello", source=SUBSCRIBER, group=True)) == []


async def test_attachments_are_deleted_after_handling(chat: Chat) -> None:
    await chat.start(admins=(ADMIN,))

    await chat.send(message("!admin look", source=STRANGER, attachment=True))

    assert chat.delete_attachment.await_count == 1


async def test_errors_are_reported_to_the_sender(chat: Chat) -> None:
    await chat.start(subscribers=(SUBSCRIBER,))
    chat.bot.db.close()  # Every query fails from now on

    [reply] = await chat.send(message("!unsubscribe", source=SUBSCRIBER))

    assert reply.text == "Something went wrong, please try again"

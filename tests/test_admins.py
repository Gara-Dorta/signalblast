from __future__ import annotations

from typing import TYPE_CHECKING

from chat_support import ADMIN, ADMIN_PASSWORD, OTHER_ADMIN, STRANGER, message

if TYPE_CHECKING:
    from chat_support import Chat


async def test_add_admin(chat: Chat) -> None:
    await chat.start(admins=(OTHER_ADMIN,))

    [reply, notice] = await chat.send(message(f"!add admin {ADMIN_PASSWORD}", source=ADMIN))

    assert reply.text == "You are now an admin! Send !help to see the admin commands"
    assert (notice.recipient, notice.text) == (OTHER_ADMIN, f"{ADMIN} is now an admin")
    assert chat.bot.db.admins() == [OTHER_ADMIN, ADMIN]

    [reply] = await chat.send(message(f"!add admin {ADMIN_PASSWORD}", source=ADMIN))
    assert reply.text == "You are already an admin"


async def test_wrong_password_alerts_the_admins_without_saying_who(chat: Chat) -> None:
    await chat.start(admins=(ADMIN,))

    [reply, alert] = await chat.send(message("!add admin guess", source=STRANGER))

    assert reply.text == "Wrong password!"
    assert (alert.recipient, alert.text) == (ADMIN, "Someone tried to become an admin with a wrong password")
    assert not chat.bot.db.is_admin(STRANGER)


async def test_admins_cannot_be_added_without_a_password(chat: Chat) -> None:
    await chat.start(password=None)

    [reply] = await chat.send(message("!add admin anything", source=STRANGER))

    assert reply.text == "Admins can't be added or removed because no admin password is set"


async def test_password_is_kept_when_it_is_not_set_on_restart(chat: Chat) -> None:
    await chat.start()
    chat.bot.db.close()
    await chat.start(password=None)

    await chat.send(message(f"!add admin {ADMIN_PASSWORD}", source=ADMIN))

    assert chat.bot.db.is_admin(ADMIN)


async def test_list_admins(chat: Chat) -> None:
    await chat.start(admins=(ADMIN, OTHER_ADMIN))

    [reply] = await chat.send(message("!list admins", source=ADMIN))

    assert reply.text == f"Admins:\n{ADMIN} (you)\n{OTHER_ADMIN}"


async def test_remove_admin(chat: Chat) -> None:
    await chat.start(admins=(ADMIN, OTHER_ADMIN))

    [reply, notice] = await chat.send(message(f"!remove admin {ADMIN_PASSWORD} {OTHER_ADMIN}", source=ADMIN))

    assert reply.text == f"Removed admin {OTHER_ADMIN}"
    assert (notice.recipient, notice.text) == (OTHER_ADMIN, "You are no longer an admin")
    assert chat.bot.db.admins() == [ADMIN]


async def test_remove_admin_checks_its_arguments(chat: Chat) -> None:
    await chat.start(admins=(ADMIN,))
    usage = "Usage: !remove admin <password> <admin id>, see the admin ids with !list admins"

    for args in ("", ADMIN, f"{ADMIN_PASSWORD} not-an-id"):
        [reply] = await chat.send(message(f"!remove admin {args}", source=ADMIN))
        assert reply.text == usage

    [reply] = await chat.send(message(f"!remove admin {ADMIN_PASSWORD} {STRANGER}", source=ADMIN))
    assert reply.text == f"{STRANGER} is not an admin"
    assert chat.bot.db.admins() == [ADMIN]


async def test_version(chat: Chat) -> None:
    await chat.start(admins=(ADMIN,))

    [reply] = await chat.send(message("!version", source=ADMIN))

    assert str(reply.text).startswith("Versions:\n\tsignalblast: ")
    assert "\n\tsignal-cli-rest-api: " in str(reply.text)

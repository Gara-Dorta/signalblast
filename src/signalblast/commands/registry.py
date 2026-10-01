from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from signalblast.commands import admins, bans, broadcast, messaging, subscription

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from signalbot import DataMessageContext

    from signalblast.broadcastbot import BroadcastBot

    Handler = Callable[[BroadcastBot, DataMessageContext, str], Awaitable[None]]


@dataclass(frozen=True)
class Command:
    trigger: str
    handler: Handler
    description: str
    args: str = ""
    # Shown in the admin section of the help
    for_admins: bool = False
    # Only admins may run it, e.g. `!add admin` is for admins but is how a user becomes one
    admin_only: bool = False

    def matches(self, text: str) -> bool:
        """Case insensitive, and the trigger must be followed by whitespace or the end of the message."""
        n = len(self.trigger)
        return text[:n].lower() == self.trigger and (len(text) == n or text[n].isspace())

    def usage(self) -> str:
        return f"{self.trigger} {self.args}".strip()


async def show_help(bot: BroadcastBot, ctx: DataMessageContext, _args: str) -> None:
    sender = ctx.message.source_uuid
    is_admin = sender is not None and bot.db.is_admin(sender)
    await bot.reply(ctx, help_message(bot, is_admin=is_admin))


COMMANDS = (
    Command("!subscribe", subscription.subscribe, "Sign up to receive the broadcasts"),
    Command("!unsubscribe", subscription.unsubscribe, "Stop receiving the broadcasts"),
    Command(
        "!broadcast",
        broadcast.broadcast_command,
        "Send a message to every subscriber, anything that isn't a command is broadcast too",
        args="<message>",
    ),
    Command("!admin", messaging.message_admins, "Send a message only to the admins", args="<message>"),
    Command("!help", show_help, "Show this message"),
    Command("!add admin", admins.add_admin, "Become an admin", args="<password>", for_admins=True),
    Command(
        "!remove admin",
        admins.remove_admin,
        "Remove an admin, see their ids with !list admins",
        args="<password> <admin id>",
        for_admins=True,
    ),
    Command("!list admins", admins.list_admins, "Show the ids of the admins", for_admins=True, admin_only=True),
    Command(
        "!ban",
        bans.ban,
        "Quote a broadcast or a message from a user and send !ban to ban its sender",
        for_admins=True,
        admin_only=True,
    ),
    Command("!list bans", bans.list_bans, "Show the banned users", for_admins=True, admin_only=True),
    Command(
        "!lift ban", bans.lift_ban, "Lift a ban, see !list bans", args="<number>", for_admins=True, admin_only=True
    ),
    Command("!version", admins.show_version, "Show the versions of the bot", for_admins=True, admin_only=True),
)

# Longest first, so that e.g. "!list admins" isn't parsed as an unknown "!list"
_BY_LENGTH = sorted(COMMANDS, key=lambda command: len(command.trigger), reverse=True)


def parse(text: str | None) -> tuple[Command, str] | None:
    """Returns the command in `text` and its arguments, None if `text` isn't a command."""
    if not text:
        return None
    text = text.strip()
    for command in _BY_LENGTH:
        if command.matches(text):
            return command, text[len(command.trigger) :].strip()
    return None


def help_message(bot: BroadcastBot, *, is_admin: bool, understood: bool = True) -> str:
    if understood:
        message = "I'm happy to help! These are the commands that you can use:\n"
    else:
        message = "I'm sorry, I didn't understand that. These are the commands that you can use:\n"

    def describe(commands: list[Command]) -> str:
        return "".join(f"\n{command.usage()}\n\t{command.description}\n" for command in commands)

    message += describe([command for command in COMMANDS if not command.for_admins])
    if is_admin:
        message += "\nAdmin commands:\n" + describe([command for command in COMMANDS if command.for_admins])
        message += "\nTo reply to a message from a user, quote it and write your reply.\n"
    if not understood:
        message += "\nTo broadcast a message that starts with !, write !broadcast before it.\n"
    if bot.settings.instructions_url is not None:
        message += (
            f"\nPlease have a look at the instructions if you haven't already:\n{bot.settings.instructions_url}\n"
        )
    return message.rstrip()

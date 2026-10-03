from __future__ import annotations

from typing import TYPE_CHECKING, override

from signalblast.commands.admins import AddAdmin, ListAdmins, RemoveAdmin, ShowVersion
from signalblast.commands.bans import Ban, LiftBan, ListBans
from signalblast.commands.base import UNKNOWN_COMMAND_PRIORITY, Command, SignalblastHandler
from signalblast.commands.broadcast import BroadcastCommand
from signalblast.commands.messaging import MessageAdmins
from signalblast.commands.subscription import Subscribe, Unsubscribe

if TYPE_CHECKING:
    from signalbot import DataMessage, DataMessageContext

    from signalblast.broadcastbot import BroadcastBot


class Help(Command):
    trigger = "!help"
    description = "Show this message"

    @override
    async def run(self, ctx: DataMessageContext, sender: str, args: str) -> None:
        await self.bot.reply(ctx, help_message(self.bot, is_admin=self.bot.db.is_admin(sender)))


class UnknownCommand(SignalblastHandler):
    """Messages that start with "!" but aren't a command get the help, so mistyped commands are not
    broadcast."""

    priority = UNKNOWN_COMMAND_PRIORITY

    @override
    def matches(self, message: DataMessage) -> bool:
        return message.text is not None and message.text.lstrip().startswith("!")

    @override
    async def handle(self, ctx: DataMessageContext, sender: str) -> None:
        await self.bot.reply(ctx, help_message(self.bot, is_admin=self.bot.db.is_admin(sender), understood=False))


# In the order they are shown in the help
COMMANDS: tuple[type[Command], ...] = (
    Subscribe,
    Unsubscribe,
    BroadcastCommand,
    MessageAdmins,
    Help,
    AddAdmin,
    RemoveAdmin,
    ListAdmins,
    Ban,
    ListBans,
    LiftBan,
    ShowVersion,
)


def help_message(bot: BroadcastBot, *, is_admin: bool, understood: bool = True) -> str:
    if understood:
        message = "I'm happy to help! These are the commands that you can use:\n"
    else:
        message = "I'm sorry, I didn't understand that. These are the commands that you can use:\n"

    def describe(commands: list[type[Command]]) -> str:
        return "".join(f"\n{command.usage()}\n\t{command.description}\n" for command in commands)

    message += describe([command for command in COMMANDS if not command.for_admins])
    message += "\nTo reply to a message from the admins, quote it and write your reply.\n"
    if is_admin:
        message += "\nAdmin commands:\n" + describe([command for command in COMMANDS if command.for_admins])
        message += "\nTo reply to a message from a user, quote it and write your reply.\n"
    if not understood:
        message += "\nTo broadcast a message that starts with !, write !broadcast before it.\n"
    if bot.settings.instructions_url is not None:
        message += "\nPlease have a look at the instructions if you haven't already:\n"
        message += f"{bot.settings.instructions_url}\n"
    return message.rstrip()

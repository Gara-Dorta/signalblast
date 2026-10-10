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
        await send_help(self.bot, sender, intro="I'm happy to help! These are the commands that you can use:")


class UnknownCommand(SignalblastHandler):
    """Messages that start with "!" but aren't a command get the help, so mistyped commands are not
    broadcast."""

    priority = UNKNOWN_COMMAND_PRIORITY

    @override
    def matches(self, message: DataMessage) -> bool:
        return message.text is not None and message.text.lstrip().startswith("!")

    @override
    async def handle(self, ctx: DataMessageContext, sender: str) -> None:
        intro = "I'm sorry, I didn't understand that. These are the commands that you can use:"
        await send_help(self.bot, sender, intro=intro, broadcast_tip=True)


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


async def send_help(
    bot: BroadcastBot,
    sender: str,
    *,
    intro: str,
    broadcast_tip: bool = False,
) -> None:
    """Replies with the help, and the admin commands in a second message if `sender` is an admin."""

    def describe(*, for_admins: bool) -> str:
        return "".join(
            f"\n{command.usage()}\n\t{command.description}\n"
            for command in COMMANDS
            if command.in_help and command.for_admins == for_admins
        )

    message = f"{intro}\n" + describe(for_admins=False)
    message += "\nTo answer a message from the admins, reply to it.\n"
    if broadcast_tip:
        message += "\nTo broadcast a message that starts with !, write !broadcast before it.\n"
    if bot.settings.instructions_url is not None:
        message += "\nPlease have a look at the instructions if you haven't already:\n"
        message += f"{bot.settings.instructions_url}\n"
    await bot.send(sender, message.rstrip())

    if bot.db.is_admin(sender):
        message = "Admin commands:\n" + describe(for_admins=True)
        message += "\nTo answer a message from a user, reply to it."
        await bot.send(sender, message)

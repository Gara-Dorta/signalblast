"""One signalbot handler per command, plus the handlers for everything that isn't a command.

Every private message is handled by exactly one of them: they are all registered with a priority, and the
matching one with the highest priority runs (see `base.py`):

1. Edits of a broadcast edit every copy of it.
2. Commands.
3. A quote of a message between a user and the admins continues that conversation, it is never broadcast.
4. Anything else starting with "!" gets the help, so mistyped commands are not broadcast.
5. Everything else is broadcast.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from signalblast.commands.broadcast import Broadcast, DeleteBroadcast, EditBroadcast
from signalblast.commands.messaging import Reply
from signalblast.commands.registry import COMMANDS, UnknownCommand

if TYPE_CHECKING:
    from signalblast.broadcastbot import BroadcastBot


def register_handlers(bot: BroadcastBot) -> None:
    for handler in (
        EditBroadcast(bot),
        *(command(bot) for command in COMMANDS),
        Reply(bot),
        UnknownCommand(bot),
        Broadcast(bot),
        DeleteBroadcast(bot),
    ):
        handler.register(bot.signal_bot)


__all__ = ["register_handlers"]

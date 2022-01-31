from enum import Enum
import re


class CommandStrings(Enum):
    subscribe = "!subscribe"
    unsubscribe = "!unsubscribe"
    broadcast = "!broadcast"


def begings_with(in_str):
    return "^(" + in_str.value + ")"


class CommandRegex(Enum):
    subscribe = re.compile(begings_with(CommandStrings.subscribe))
    unsubscribe = re.compile(begings_with(CommandStrings.unsubscribe))
    broadcast = re.compile(begings_with(CommandStrings.broadcast))

from enum import Enum
import re


class CommandStrings(Enum):
    subscribe = "!subscribe"
    unsubscribe = "!unsubscribe"
    broadcast = "!broadcast"


class CommandRegex(Enum):
    def _begings_with(in_str):
        return "^(" + in_str.value + ")"

    subscribe = re.compile(_begings_with(CommandStrings.subscribe))
    unsubscribe = re.compile(_begings_with(CommandStrings.unsubscribe))
    broadcast = re.compile(_begings_with(CommandStrings.broadcast))

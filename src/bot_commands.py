from enum import Enum
import re


class PublicCommandStrings(Enum):
    subscribe = "!subscribe"
    unsubscribe = "!unsubscribe"
    broadcast = "!broadcast"
    msg_to_admin = "!admin"


class AdminCommandStrings(Enum):
    add_admin = "!add admin"
    remove_admin = "!remove admin"
    msg_from_admin = "!reply"
    ban_subscriber = "!ban"
    lift_ban_subscriber = "!lift ban"


class CommandRegex(Enum):
    def _begings_with(in_str):
        return "^(" + in_str.value + ")"

    subscribe = re.compile(_begings_with(PublicCommandStrings.subscribe))
    unsubscribe = re.compile(_begings_with(PublicCommandStrings.unsubscribe))
    broadcast = re.compile(_begings_with(PublicCommandStrings.broadcast))
    add_admin = re.compile(_begings_with(AdminCommandStrings.add_admin))
    remove_admin = re.compile(_begings_with(AdminCommandStrings.remove_admin))
    msg_to_admin = re.compile(_begings_with(PublicCommandStrings.msg_to_admin))
    msg_from_admin = re.compile(_begings_with(AdminCommandStrings.msg_from_admin))
    ban_subscriber = re.compile(_begings_with(AdminCommandStrings.ban_subscriber))
    lift_ban_subscriber = re.compile(_begings_with(AdminCommandStrings.lift_ban_subscriber))

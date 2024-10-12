import inspect
import re
from collections.abc import Iterator
from dataclasses import dataclass


class _IterableDataClass:
    _public_attr = None

    @classmethod
    def _get_public_attributes(cls) -> None:
        cls._public_attr: list[str] = []
        for attr, value in inspect.getmembers(cls):
            if not (attr.startswith("_") or inspect.ismethod(value)):
                cls._public_attr.append(value)

    def __iter__(self) -> Iterator[str]:
        if self._public_attr is None:
            self._get_public_attributes()

        yield from self._public_attr


@dataclass
class _PublicCommandStrings(_IterableDataClass):
    subscribe = "!subscribe"
    unsubscribe = "!unsubscribe"
    broadcast = "!broadcast"
    msg_to_admin = "!admin"
    help = "!help"


PublicCommandStrings = _PublicCommandStrings()


@dataclass
class _AdminCommandStrings(_IterableDataClass):
    add_admin = "!add admin"
    remove_admin = "!remove admin"
    msg_from_admin = "!reply"
    ban_subscriber = "!ban"
    lift_ban_subscriber = "!lift ban"
    set_ping = "!set ping"
    unset_ping = "!unset ping"
    last_msg_user_uuid = "!last msg user uuid"


AdminCommandStrings = _AdminCommandStrings()


@dataclass
class _AdminCommandArgs(_IterableDataClass):
    add_admin = "<password>"
    remove_admin = "<password>"
    msg_from_admin = "<user id>"
    ban_subscriber = "<user id>"
    lift_ban_subscriber = "<user id>"
    set_ping = "<time>"
    unset_ping = ""
    last_msg_user_uuid = ""


AdminCommandArgs = _AdminCommandArgs()


def _begings_with(in_str: str) -> str:
    return "^(" + in_str + ")"


@dataclass
class _CommandRegex(_IterableDataClass):
    subscribe = re.compile(_begings_with(PublicCommandStrings.subscribe))
    unsubscribe = re.compile(_begings_with(PublicCommandStrings.unsubscribe))
    broadcast = re.compile(_begings_with(PublicCommandStrings.broadcast))
    add_admin = re.compile(_begings_with(AdminCommandStrings.add_admin))
    remove_admin = re.compile(_begings_with(AdminCommandStrings.remove_admin))
    msg_to_admin = re.compile(_begings_with(PublicCommandStrings.msg_to_admin))
    msg_from_admin = re.compile(_begings_with(AdminCommandStrings.msg_from_admin))
    ban_subscriber = re.compile(_begings_with(AdminCommandStrings.ban_subscriber))
    lift_ban_subscriber = re.compile(_begings_with(AdminCommandStrings.lift_ban_subscriber))
    set_ping = re.compile(_begings_with(AdminCommandStrings.set_ping))
    unset_ping = re.compile(_begings_with(AdminCommandStrings.unset_ping))
    help = re.compile(_begings_with(PublicCommandStrings.help))
    last_msg_user_uuid = re.compile(_begings_with(AdminCommandStrings.last_msg_user_uuid))


CommandRegex = _CommandRegex()

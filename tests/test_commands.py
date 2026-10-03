from __future__ import annotations

from signalblast.commands.registry import COMMANDS


def test_every_command_matches_only_its_own_trigger() -> None:
    # Commands share a priority, so a message must never match two of them
    for command in COMMANDS:
        text = f"{command.usage()} something"
        assert [other for other in COMMANDS if other.parse(text) is not None] == [command]


def test_commands_match_case_insensitively_and_only_whole_words() -> None:
    for command in COMMANDS:
        assert command.parse(command.trigger.upper()) == ""
        assert command.parse(f"  {command.trigger}  args ") == "args"
        assert command.parse(f"{command.trigger}x") is None

from pathlib import Path

from signalblast.commands_strings import AdminCommandArgs, AdminCommandStrings, PublicCommandStrings


class MessageHandler:
    def __init__(self, attachments_folder: Path) -> None:
        self.attachments_folder = attachments_folder

    @staticmethod
    def remove_command_from_message(message: str | None, command: str) -> str | None:
        if message == "" or message is None:
            return None
        message = message.replace(command, "", 1).strip()
        if message == "":
            return None
        return message

    def empty_list_to_none(self, attachments: list[str] | None) -> list | None:
        if attachments == []:
            return None

        return attachments

    def delete_attachments(self, attachments: list[str] | None, link_previews: list[str] | None) -> None:
        if attachments is not None:
            for attachment in attachments:
                (self.attachments_folder / attachment).unlink()

        if link_previews is not None:
            error_msg = "Link previews are not implemented yet"
            for _ in link_previews:
                raise NotImplementedError(error_msg)

    @staticmethod
    def _compose_help_message(*, add_admin_commands: bool) -> str:
        def _add_commands(message: str) -> str:
            for command_str in PublicCommandStrings:
                message += "\t" + command_str + "\n"
            return message

        def _add_admin_commands(message: str) -> str:
            for command_str, command_arg in zip(AdminCommandStrings, AdminCommandArgs, strict=False):
                message += "\t" + command_str + " " + command_arg + "\n"
            return message

        message = _add_commands("")
        if add_admin_commands:
            message = _add_admin_commands(message)
        return message

    @staticmethod
    def compose_help_message(*, add_admin_commands: bool = False, is_help: bool = True) -> str:
        message = MessageHandler._compose_help_message(add_admin_commands=add_admin_commands)
        if is_help:
            return "I'm happy to help! This are the commands that you can use:\n\n" + message
        message = "I'm sorry, I didn't understand you but I understand the following commands:\n\n" + message
        message += "\nPlease try again"
        return message

    @staticmethod
    def compose_must_subscribe_message() -> str:
        message = "To be able to send messages you must sign up.\n"
        message += "Please sign up by sending:\n"
        message += f"\t{PublicCommandStrings.subscribe}\n"
        message += "and try again after that."
        return message

    @staticmethod
    def compose_message_to_admin(message: str, user: str | None) -> str:
        header = "***Admin***\n"
        if user is not None:
            header += user + "\n"
        return header + message

    @staticmethod
    def compose_welcome_message(default_message: str | None) -> str:
        if default_message is None:
            return "Subscription successful!"
        return default_message

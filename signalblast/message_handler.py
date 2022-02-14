import os
from typing import Optional, List
from semaphore import Attachment

from bot_commands import AdminCommandStrings, PublicCommandStrings, AdminCommandArgs


class MessageHandler():
    def __init__(self) -> None:
        pass

    @staticmethod
    def remove_command_from_message(message: str, command: str) -> str:
        if message == '':
            return None
        else:
            message = message.replace(command, '', 1).strip()
            if message == '':
                return None
            else:
                return message

    def prepare_attachments(self, attachments: Optional[List[Attachment]]) -> List:
        if attachments == []:
            return None

        attachments_to_send = []
        for attachment in attachments:
            attachment_to_send = {"filename": attachment.stored_filename,
                                  "customFilename": attachment.custom_filename,
                                  "width": attachment.width,
                                  "height": attachment.height,
                                  "contentType": attachment.content_type,
                                  }
            attachments_to_send.append(attachment_to_send)

        return attachments_to_send

    def delete_attachments(self, attachments: Optional[List[dict]]):
        if attachments is None:
            return

        for attachment in attachments:
            os.remove(attachment["filename"])

    @staticmethod
    def _compose_help_message(add_admin_commands: bool) -> str:
        def _add_commands(message):
            for command_str in PublicCommandStrings:
                message += "\t" + command_str + "\n"
            return message

        def _add_admin_commands(message):
            for command_str, command_arg in zip(AdminCommandStrings, AdminCommandArgs):
                message += "\t" + command_str + " " + command_arg + "\n"
            return message

        message = _add_commands('')
        if add_admin_commands:
            message = _add_admin_commands(message)
        return message

    @staticmethod
    def compose_help_message(add_admin_commands: bool = False, is_help: bool = True) -> str:
        message = MessageHandler._compose_help_message(add_admin_commands)
        if is_help:
            return "I'm happy to help! This are the commands that you can use:\n\n" + message
        else:
            message = "I'm sorry, I didn't understand you but I understand the following commands:\n\n" + message
            message += "\nPlease try again"
            return message

    @staticmethod
    def compose_must_subscribe_message() -> str:
        message = "To be able to send messages you must be a subscriber too.\n"
        message += "Please subscribe by sending:\n"
        message += f"\t{PublicCommandStrings.subscribe}\n"
        message += "and try again after that."
        return message

    @staticmethod
    def compose_message_to_admin(message: str, user: Optional[str]) -> str:
        header = "***Admin***\n"
        if user is not None:
            header += user + "\n"
        return header + message

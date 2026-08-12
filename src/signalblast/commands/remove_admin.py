from signalbot import DataMessageContext, DataMessageHandler, ReceiptType, SendMessage, regex_triggered

from signalblast.broadcastbot import BroadcasBot
from signalblast.commands_strings import AdminCommandStrings, CommandRegex


class RemoveAdmin(DataMessageHandler):
    def __init__(self, bot: BroadcasBot) -> None:
        super().__init__()
        self.broadcastbot = bot

    @regex_triggered(CommandRegex.remove_admin)
    async def handle_data_message(self, context: DataMessageContext) -> None:
        try:
            await context.send_receipt(ReceiptType.READ)

            subscriber_uuid = context.message.source_uuid
            password = self.broadcastbot.message_handler.remove_command_from_message(
                context.message.text,
                AdminCommandStrings.remove_admin,
            )

            previous_admin = self.broadcastbot.admin.admin_id
            if await self.broadcastbot.admin.remove(password):
                await self.broadcastbot.reply_with_warn_on_failure(context, "Admin has been removed!")
                if previous_admin is not None and subscriber_uuid != previous_admin:
                    msg_to_admin = self.broadcastbot.message_handler.compose_message_to_admin(
                        "You are no longer an admin!",
                        subscriber_uuid,
                    )
                    await context.bot.messages.send(SendMessage(text=msg_to_admin), previous_admin)
                self.broadcastbot.logger.info("%s is no longer an admin", previous_admin)
            else:
                await self.broadcastbot.reply_with_warn_on_failure(
                    context,
                    "Removing failed: admin password is incorrect!",
                )
                if previous_admin is not None:
                    msg_to_admin = self.broadcastbot.message_handler.compose_message_to_admin(
                        "Tried to remove you as admin",
                        subscriber_uuid,
                    )
                    await context.bot.messages.send(SendMessage(text=msg_to_admin), previous_admin)
                self.broadcastbot.logger.warning("Failed password check for remove_admin %s", subscriber_uuid)
        except Exception:
            self.broadcastbot.logger.exception("")

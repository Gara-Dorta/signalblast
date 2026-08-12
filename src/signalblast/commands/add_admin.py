from signalbot import DataMessageContext, DataMessageHandler, ReceiptType, SendMessage, regex_triggered

from signalblast.broadcastbot import BroadcasBot
from signalblast.commands_strings import AdminCommandStrings, CommandRegex


class AddAdmin(DataMessageHandler):
    def __init__(self, bot: BroadcasBot) -> None:
        super().__init__()
        self.broadcastbot = bot

    @regex_triggered(CommandRegex.add_admin)
    async def handle_data_message(self, context: DataMessageContext) -> None:
        try:
            await context.send_receipt(ReceiptType.READ)

            subscriber_uuid = context.message.source_uuid
            password = self.broadcastbot.message_handler.remove_command_from_message(
                context.message.text,
                AdminCommandStrings.add_admin,
            )

            previous_admin = self.broadcastbot.admin.admin_id
            if await self.broadcastbot.admin.add(subscriber_uuid, password):
                await self.broadcastbot.reply_with_warn_on_failure(context, "You have been added as admin!")
                if previous_admin is not None and subscriber_uuid != previous_admin:
                    msg_to_admin = self.broadcastbot.message_handler.compose_message_to_admin(
                        "You are no longer an admin!",
                        subscriber_uuid,
                    )
                    await context.bot.messages.send(SendMessage(text=msg_to_admin), previous_admin)
                log_message = f"Previous admin was {previous_admin}, new admin is {subscriber_uuid}"
                self.broadcastbot.logger.info(log_message)
            else:
                await self.broadcastbot.reply_with_warn_on_failure(
                    context,
                    "Adding failed, admin password is incorrect!",
                )
                if previous_admin is not None:
                    msg_to_admin = self.broadcastbot.message_handler.compose_message_to_admin(
                        "Tried to be added as admin",
                        subscriber_uuid,
                    )
                    await context.bot.messages.send(SendMessage(text=msg_to_admin), previous_admin)
                self.broadcastbot.logger.warning("%s failed password check for add_admin", subscriber_uuid)
        except Exception:
            self.broadcastbot.logger.exception("")

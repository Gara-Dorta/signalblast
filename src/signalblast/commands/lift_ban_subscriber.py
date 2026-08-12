from signalbot import DataMessageContext, DataMessageHandler, ReceiptType, SendMessage, regex_triggered

from signalblast.broadcastbot import BroadcasBot
from signalblast.commands_strings import AdminCommandStrings, CommandRegex


class LiftBanSubscriber(DataMessageHandler):
    def __init__(self, bot: BroadcasBot) -> None:
        super().__init__()
        self.broadcastbot = bot

    @regex_triggered(CommandRegex.lift_ban_subscriber)
    async def handle_data_message(self, context: DataMessageContext) -> None:
        try:
            await context.send_receipt(ReceiptType.READ)

            user_id = self.broadcastbot.message_handler.remove_command_from_message(
                context.message.text,
                AdminCommandStrings.lift_ban_subscriber,
            )

            if not await self.broadcastbot.is_user_admin(context, AdminCommandStrings.lift_ban_subscriber):
                return

            if user_id in self.broadcastbot.banned_users:
                await self.broadcastbot.banned_users.remove(user_id)
            else:
                await self.broadcastbot.reply_with_warn_on_failure(
                    context,
                    "Could not lift the ban because the user was not banned",
                )
                self.broadcastbot.logger.info("Could not lift the ban of %s because the user was not banned", user_id)
                return

            await context.bot.messages.send(
                SendMessage(text="You have banned have been lifted, try subscribing again"),
                user_id,
            )
            await self.broadcastbot.reply_with_warn_on_failure(context, "Successfully lifted the ban on the user")

            self.broadcastbot.logger.info("Lifted the ban on user %s", user_id)
        except Exception:
            self.broadcastbot.logger.exception("")
            try:
                await self.broadcastbot.reply_with_warn_on_failure(context, "Failed lift the ban on the user")
            except Exception:
                self.broadcastbot.logger.exception("")

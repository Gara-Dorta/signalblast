from signalbot import Command
from signalbot import Context as ChatContext

from signalblast.broadcastbot import BroadcasBot
from signalblast.commands_strings import AdminCommandStrings, CommandRegex
from signalblast.utils import triggered


class LiftBanSubscriber(Command):
    def __init__(self, bot: BroadcasBot) -> None:
        super().__init__()
        self.broadcastbot = bot

    @triggered(CommandRegex.lift_ban_subscriber)
    async def handle(self, ctx: ChatContext) -> None:
        try:
            user_id = self.broadcastbot.message_handler.remove_command_from_message(
                ctx.message.text, AdminCommandStrings.lift_ban_subscriber
            )

            if not await self.broadcastbot.is_user_admin(ctx, AdminCommandStrings.lift_ban_subscriber):
                return

            if user_id in self.broadcastbot.banned_users:
                await self.broadcastbot.banned_users.remove(user_id)
            else:
                await self.broadcastbot.reply_with_warn_on_failure(
                    ctx, "Could not lift the ban because the user was not banned"
                )
                self.broadcastbot.logger.info(f"Could not lift the ban of {user_id} because the user was not banned")
                return

            await self.broadcastbot.send(user_id, "You have banned have been lifted, try subscribing again")
            await self.broadcastbot.reply_with_warn_on_failure(ctx, "Successfully lifted the ban on the user")

            self.broadcastbot.logger.info(f"Lifted the ban on user {user_id}")
        except Exception as e:
            self.broadcastbot.logger.error(e, exc_info=True)
            try:
                await self.broadcastbot.reply_with_warn_on_failure(ctx, "Failed lift the ban on the user")
            except Exception as e:
                self.broadcastbot.logger.error(e, exc_info=True)

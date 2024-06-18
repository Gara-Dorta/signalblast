from asyncio import gather
from typing import Optional
from logging import Logger
from time import time
from pathlib import Path

from admin import Admin
from users import Users
from bot_commands import CommandRegex, AdminCommandStrings, PublicCommandStrings
from message_handler import MessageHandler
from utils import get_code_data_path
from signalbot import Command #, triggered
from signalbot import Context as ChatContext
from signalbot import SignalBot
import functools
from re import Pattern

def triggered(pattern: Pattern):
    def decorator_triggered(func):
        @functools.wraps(func)
        async def wrapper_triggered(*args, **kwargs):
            c: ChatContext = args[1]
            text = c.message.text
            if not isinstance(text, str):
                return

            if pattern.match(text) is None:
                return

            return await func(*args, **kwargs)

        return wrapper_triggered

    return decorator_triggered

class BotAnswers(SignalBot):
    subscribers_data_path = get_code_data_path() / 'subscribers.csv'
    banned_users_data_path = get_code_data_path() / 'banned_users.csv'


    def __init__(self, config: dict):
        super().__init__(config)
        self.subscribers: Users = None
        self.banned_users: Users = None
        self.admin: Admin = None
        self.message_handler: MessageHandler = None
        self.help_message: str = None
        self.wrong_command_message: str = None
        self.admin_help_message: str = None
        self.admin_wrong_command_message: str = None
        self.must_subscribe_message: str = None
        self.logger: Logger = None
        self.expiration_time = None
        # self.ping_job: Job = None


    async def load_data(self, logger: Logger, admin_pass: Optional[str], expiration_time: Optional[int],
                     signald_data_path: Path):
        self.subscribers = await Users.load_from_file(self.subscribers_data_path)
        self.banned_users = await Users.load_from_file(self.banned_users_data_path)

        self.admin = await Admin.load_from_file(admin_pass)
        self.message_handler = MessageHandler(signald_data_path / 'attachments')

        self.help_message = self.message_handler.compose_help_message(is_help=True)
        self.wrong_command_message = self.message_handler.compose_help_message(is_help=False)
        self.admin_help_message = self.message_handler.compose_help_message(add_admin_commands=True)
        self.admin_wrong_command_message = self.message_handler.compose_help_message(add_admin_commands=True,
                                                                                     is_help=False)

        self.must_subscribe_message = self.message_handler.compose_must_subscribe_message()

        self.expiration_time = expiration_time

        self.logger = logger
        self.logger.debug('BotAnswers is initialised')

    async def reply_with_warn_on_failure(self, ctx: ChatContext, message: str) -> bool:
        if await ctx.reply(message):
            return True
        else:
            self.logger.warning(f"Could not send message to {ctx.message.source_uuid}")
            return False

    async def is_user_admin(self, ctx: ChatContext, command: str) -> bool:
        subscriber_uuid = ctx.message.source_uuid
        if self.admin.admin_id is None:
            await self.reply_with_warn_on_failure(ctx, "I'm sorry but there are no admins")
            self.logger.info(f"Tried to {command} but there are no admins! {subscriber_uuid}")
            return False

        if self.admin.admin_id != subscriber_uuid:
            await self.reply_with_warn_on_failure(ctx, "I'm sorry but you are not an admin")
            msg_to_admin = self.message_handler.compose_message_to_admin(f'Tried to {command}', subscriber_uuid)
            await self.send(self.admin.admin_id, msg_to_admin)
            self.logger.info(f"{subscriber_uuid} tried to {command} but admin is {self.admin.admin_id}")
            return False

        return True

class Subscribe(Command):
    def __init__(self, bot: BotAnswers) -> None:
        super().__init__()
        self.bot = bot

    @triggered(CommandRegex.subscribe)
    async def handle(self, ctx: ChatContext) -> None:
        try:
            subscriber_uuid = ctx.message.source_uuid
            if subscriber_uuid in self.bot.subscribers:
                await self.bot.reply_with_warn_on_failure(ctx, "Already subscribed!")
                self.bot.logger.info("Already subscribed!")
                return

            if subscriber_uuid in self.bot.banned_users:
                await self.bot.reply_with_warn_on_failure(ctx, "This number is not allowed to subscribe")
                self.bot.logger.info(f"{subscriber_uuid} was not allowed to subscribe")
                return

            await self.bot.subscribers.add(subscriber_uuid, ctx.message.source_number)
            await self.bot.reply_with_warn_on_failure(ctx, "Subscription successful!")
            # if self.bot.expiration_time is not None:
            #     await ctx.bot.set_expiration(subscriber_uuid, self.bot.expiration_time)
            self.bot.logger.info(f"{subscriber_uuid} subscribed")
        except Exception as e:
            self.bot.logger.error(e, exc_info=True)
            try:
                await self.bot.reply_with_warn_on_failure(ctx, "Could not subscribe!")
            except Exception as e:
                self.bot.logger.error(e, exc_info=True)
        # finally:
        #     raise StopPropagation

class Unsubscribe(Command):
    def __init__(self, bot: BotAnswers) -> None:
        super().__init__()
        self.bot = bot

    @triggered(CommandRegex.unsubscribe)
    async def handle(self, ctx: ChatContext) -> None:
        try:
            subscriber_uuid = ctx.message.source_uuid

            if subscriber_uuid not in self.bot.subscribers:
                await self.bot.reply_with_warn_on_failure(ctx, "Not subscribed!")
                self.bot.logger.info(f"{subscriber_uuid} tried to unsubscribe but they are not subscribed")
                return

            await self.bot.subscribers.remove(subscriber_uuid)
            await self.bot.reply_with_warn_on_failure(ctx, "Successfully unsubscribed!")
            self.bot.logger.info(f"{subscriber_uuid} unsubscribed")
        except Exception as e:
            self.bot.logger.error(e, exc_info=True)
            try:
                await self.bot.reply_with_warn_on_failure(ctx, "Could not unsubscribe!")
            except Exception as e:
                self.bot.logger.error(e, exc_info=True)
        # finally:
        #     raise StopPropagation

class Broadcast(Command):
    def __init__(self, bot: BotAnswers) -> None:
        super().__init__()
        self.bot = bot

    @staticmethod
    async def broadcast(bot: BotAnswers, ctx: ChatContext) -> None:
        num_broadcasts = 0
        num_subscribers = -1

        try:
            subscriber_uuid = ctx.message.source_uuid
            if subscriber_uuid in bot.banned_users:
                await bot.send(subscriber_uuid, "This number is not allowed to broadcast messages")
                bot.logger.info(f"{subscriber_uuid} tried to broadcast but they are banned")
                return

            if subscriber_uuid not in bot.subscribers:
                await bot.send(subscriber_uuid, bot.must_subscribe_message)
                bot.logger.info(f"{subscriber_uuid} tried to broadcast but they are not subscribed")
                return

            num_subscribers = len(bot.subscribers)

            # await ctx.message.mark_read()
            message = bot.message_handler.remove_command_from_message(ctx.message.text,
                                                                       PublicCommandStrings.broadcast)
            attachments = bot.message_handler.empty_list_to_none(ctx.message.base64_attachments)
            # link_previews = bot.message_handler.empty_list_to_none(ctx.message.data_message.previews)

            if message is None and attachments is None:
                return

            if message is None:
                message = ''

            # Broadcast message to all subscribers.
            send_tasks = [None] * len(bot.subscribers)

            for i, subscriber in enumerate(bot.subscribers):
                # This only works with phone numbers and not with UUIDs
                send_tasks[i] = bot.send(subscriber, message, base64_attachments=attachments)
                                                    #  link_previews=link_previews)

            send_task_results = await gather(*send_tasks)

            for send_task_result in send_task_results:
                if send_task_result:
                    num_broadcasts += 1
                    bot.logger.info(f"Message successfully sent to {subscriber}")
                else:
                    bot.logger.warning(f"Could not send message to {subscriber}")
                    await bot.subscribers.remove(ctx.message.source_uuid)

            bot.message_handler.delete_attachments(attachments, link_previews=None)

            await bot.reply_with_warn_on_failure(ctx, f"Message sent to {num_broadcasts} subscribers")
        except Exception as e:
            bot.logger.error(e, exc_info=True)
            try:
                error_str = "Something went wrong when sending the message"
                if num_broadcasts == num_subscribers:
                    error_str += ", but it was sent to everybody"
                error_str += ", please contact the admin if the problem persists"
                await bot.reply_with_warn_on_failure(ctx, error_str)
            except Exception as e:
                bot.logger.error(e, exc_info=True)
        # finally:
        #     raise StopPropagation

    @triggered(CommandRegex.broadcast)
    async def handle(self, ctx: ChatContext) -> None:
        Broadcast.broadcast(self.bot, ctx)



class DisplayHelp(Command):
    def __init__(self, bot: BotAnswers) -> None:
        super().__init__()
        self.bot = bot

    def _get_help_message(self, input_message: str, subscriber_uuid: str) -> str:
        if input_message.startswith(PublicCommandStrings.help):
            is_wrong_command = False
        else:
            is_wrong_command = True

        if subscriber_uuid != self.bot.admin.admin_id:
            if is_wrong_command:
                return self.bot.wrong_command_message
            else:
                return self.bot.help_message
        else:
            if is_wrong_command:
                return self.bot.admin_wrong_command_message
            else:
                return self.bot.admin_help_message

    def is_valid_command(self, message: str) -> bool:
            regex: Pattern
            for regex in CommandRegex:
                if regex.search(message) is not None:
                    return True                
            return False

    async def handle(self, ctx: ChatContext) -> None:
        try:
            subscriber_uuid = ctx.message.source_uuid
            message = ctx.message.text
            if message == None:
                if ctx.message.base64_attachments == []:
                    self.bot.logger.info(f"Received reaction, sticker or similar from {subscriber_uuid}")
                    return

                # Only attachment, assume the user wants to forward that
                self.bot.logger.info(f"Received a file from {subscriber_uuid}, broadcasting!")
                await Broadcast.broadcast(self.bot, ctx)
                return

            if self.is_valid_command(message):
                return
            
            help_message = self._get_help_message(message, subscriber_uuid)

            await self.bot.reply_with_warn_on_failure(ctx, help_message)
            self.bot.logger.info(f"Sent help message to {subscriber_uuid}")
        except Exception as e:
            # if isinstance(e, StopPropagation):
            #     raise
            self.bot.logger.error(e, exc_info=True)

class AddAdmin(Command):
    def __init__(self, bot: BotAnswers) -> None:
        super().__init__()
        self.bot = bot

    @triggered(CommandRegex.add_admin)
    async def handle(self, ctx: ChatContext) -> None:
        try:
            subscriber_uuid = ctx.message.source_uuid
            password = self.bot.message_handler.remove_command_from_message(ctx.message.get_body(),
                                                                        AdminCommandStrings.add_admin)

            previous_admin = self.bot.admin.admin_id
            if await self.bot.admin.add(subscriber_uuid, password):
                await self.bot.reply_with_warn_on_failure(ctx, 'You have been added as admin!')
                if previous_admin is not None and subscriber_uuid != previous_admin:
                    msg_to_admin = self.bot.message_handler.compose_message_to_admin('You are no longer an admin!',
                                                                                 subscriber_uuid)
                    await self.bot.send(previous_admin, msg_to_admin)
                log_message = f"Previous admin was {previous_admin}, new admin is {subscriber_uuid}"
                self.bot.logger.info(log_message)
            else:
                await self.bot.reply_with_warn_on_failure(ctx, 'Adding failed, admin password is incorrect!')
                if previous_admin is not None:
                    msg_to_admin = self.bot.message_handler.compose_message_to_admin('Tried to be added as admin',
                                                                                 subscriber_uuid)
                    await self.bot.send(previous_admin, msg_to_admin)
                self.bot.logger.warning(f"{subscriber_uuid} failed password check for add_admin")
        except Exception as e:
            self.bot.logger.error(e, exc_info=True)
        # finally:
        #     raise StopPropagation
        
class RemoveAdmin(Command):
    def __init__(self, bot: BotAnswers) -> None:
        super().__init__()
        self.bot = bot

    @triggered(CommandRegex.remove_admin)
    async def handle(self, ctx: ChatContext) -> None:
        try:
            subscriber_uuid = ctx.message.source_uuid
            password = self.bot.message_handler.remove_command_from_message(ctx.message.get_body(),
                                                                        AdminCommandStrings.remove_admin)

            previous_admin = self.bot.admin.admin_id
            if await self.bot.admin.remove(password):
                await self.bot.reply_with_warn_on_failure(ctx, 'Admin has been removed!')
                if previous_admin is not None and subscriber_uuid != previous_admin:
                    msg_to_admin = self.bot.message_handler.compose_message_to_admin('You are no longer an admin!',
                                                                                 subscriber_uuid)
                    await self.bot.send(previous_admin, msg_to_admin)
                self.bot.logger.info(f"{previous_admin} is no longer an admin")
            else:
                await self.bot.reply_with_warn_on_failure(ctx, 'Removing failed: admin password is incorrect!')
                if previous_admin is not None:
                    msg_to_admin = self.bot.message_handler.compose_message_to_admin('Tried to remove you as admin',
                                                                                 subscriber_uuid)
                    await self.bot.send(previous_admin, msg_to_admin)
                self.bot.logger.warning(f"Failed password check for remove_admin {subscriber_uuid}")
        except Exception as e:
            self.bot.logger.error(e, exc_info=True)
        # finally:
        #     raise StopPropagation

class MessageToAdmin(Command):
    def __init__(self, bot: BotAnswers) -> None:
        super().__init__()
        self.bot = bot

    @triggered(CommandRegex.msg_to_admin)
    async def handle(self, ctx: ChatContext) -> None:
        try:
            subscriber_uuid = ctx.message.source_uuid
            message = self.bot.message_handler.remove_command_from_message(ctx.message.get_body(),
                                                                       PublicCommandStrings.msg_to_admin)

            if self.bot.admin.admin_id is None:
                await self.bot.reply_with_warn_on_failure(ctx, "I'm sorry but there are no admins to contact!")
                self.bot.logger.info(f"Tried to contact an admin but there is none! {subscriber_uuid}")
                return

            if subscriber_uuid in self.bot.banned_users:
                await self.bot.reply_with_warn_on_failure(ctx, "You are not allowed to contact the admin!")
                self.bot.logger.info(f"Banned user {subscriber_uuid} tried to contact admin")
                return

            msg_to_admin = self.bot.message_handler.compose_message_to_admin('Sent you message:\n', subscriber_uuid)
            msg_to_admin += message
            attachments = self.bot.message_handler.empty_list_to_none(ctx.message.data_message.attachments)
            await self.bot.send(self.bot.admin.admin_id, msg_to_admin, attachments=attachments)
            self.bot.logger.info(f"Sent message from {subscriber_uuid} to admin {self.bot.admin.admin_id}")
        except Exception as e:
            self.bot.logger.error(e, exc_info=True)
            try:
                await self.bot.reply_with_warn_on_failure(ctx, "Failed to send the message to the admin!")
            except Exception as e:
                self.bot.logger.error(e, exc_info=True)
        # finally:
        #     raise StopPropagation



class MessageFromAdmin(Command):
    def __init__(self, bot: BotAnswers) -> None:
        super().__init__()
        self.bot = bot

    @triggered(CommandRegex.msg_from_admin)
    async def handle(self, ctx: ChatContext) -> None:
        try:
            message = self.bot.message_handler.remove_command_from_message(ctx.message.get_body(),
                                                                       AdminCommandStrings.msg_from_admin)

            if not await self.bot.is_user_admin(ctx, AdminCommandStrings.ban_subscriber):
                return

            user_id, message = message.split(' ', 1)

            if user_id not in self.bot.subscribers:
                if ' ' in message:
                    confirmation, message = message.split(' ', 1)
                else:
                    confirmation = None
                if confirmation != '!force':
                    warn_message = "User is not in subscribers list, use !reply <uuid> !force to message them"
                    await self.bot.reply_with_warn_on_failure(ctx, warn_message)
                    return

            message = 'Admin: ' + message
            attachments = self.bot.message_handler.empty_list_to_none(ctx.message.data_message.attachments)

            await self.bot.send(user_id, message, attachments=attachments)
            self.bot.logger.info(f"Sent message from admin {self.bot.admin.admin_id} to user {user_id}")
        except Exception as e:
            self.bot.logger.error(e, exc_info=True)
            try:
                await self.bot.reply_with_warn_on_failure(ctx, "Failed to send the message to the user!")
            except Exception as e:
                self.bot.logger.error(e, exc_info=True)
        # finally:
        #     raise StopPropagation

class BanSubscriber(Command):
    def __init__(self, bot: BotAnswers) -> None:
        super().__init__()
        self.bot = bot

    @triggered(CommandRegex.ban_subscriber)
    async def handle(self, ctx: ChatContext) -> None:
        try:
            user_id = self.bot.message_handler.remove_command_from_message(ctx.message.get_body(),
                                                                       AdminCommandStrings.ban_subscriber)

            if not await self.is_user_admin(ctx, AdminCommandStrings.ban_subscriber):
                return

            user_phonenumber = self.bot.subscribers.get_phone_number(user_id)
            if user_id in self.bot.subscribers:
                await self.bot.subscribers.remove(user_id)
            await self.bot.banned_users.add(user_id, user_phonenumber)

            await self.bot.send(user_id, 'You have been banned')
            await self.bot.reply_with_warn_on_failure(ctx, "Successfully banned user")

            self.bot.logger.info(f"Banned user {user_id}")
        except Exception as e:
            self.bot.logger.error(e, exc_info=True)
            try:
                await self.bot.reply_with_warn_on_failure(ctx, "Failed to ban user")
            except Exception as e:
                self.bot.logger.error(e, exc_info=True)
        # finally:
        #     raise StopPropagation

class LiftBanSubscriber(Command):
    def __init__(self, bot: BotAnswers) -> None:
        super().__init__()
        self.bot = bot

    @triggered(CommandRegex.lift_ban_subscriber)
    async def handle(self, ctx: ChatContext) -> None:
        try:
            user_id = self.bot.message_handler.remove_command_from_message(ctx.message.get_body(),
                                                                       AdminCommandStrings.lift_ban_subscriber)

            if not await self.is_user_admin(ctx, AdminCommandStrings.lift_ban_subscriber):
                return

            if user_id in self.bot.banned_users:
                await self.bot.banned_users.remove(user_id)
            else:
                await self.bot.reply_with_warn_on_failure(ctx, "Could not lift the ban because the user was not banned")
                self.bot.logger.info(f"Could not lift the ban of {user_id} because the user was not banned")
                return

            await self.bot.send(user_id, 'You have banned have been lifted, try subscribing again')
            await self.bot.reply_with_warn_on_failure(ctx, "Successfully lifted the ban on the user")

            self.bot.logger.info(f"Lifted the ban on user {user_id}")
        except Exception as e:
            self.bot.logger.error(e, exc_info=True)
            try:
                await self.bot.reply_with_warn_on_failure(ctx, "Failed lift the ban on the user")
            except Exception as e:
                self.bot.logger.error(e, exc_info=True)
        # finally:
        #     raise StopPropagation



class SetPing(Command):
    def __init__(self, bot: BotAnswers) -> None:
        super().__init__()
        self.bot = bot

    async def _send_ping(self, ctx: ChatContext) -> None:
        try:
            await self.bot.reply_with_warn_on_failure(ctx, "Ping")
        except Exception as e:
            self.bot.logger.error(e, exc_info=True)
            try:
                await self.bot.reply_with_warn_on_failure(ctx, "Failed to send ping")
            except Exception as e:
                self.bot.logger.error(e, exc_info=True)

    @triggered(CommandRegex.set_ping)
    async def handle(self, ctx: ChatContext) -> None:
        try:
            ping_time = self.bot.message_handler.remove_command_from_message(ctx.message.get_body(),
                                                                       AdminCommandStrings.set_ping)

            if not await self.is_user_admin(ctx, AdminCommandStrings.lift_ban_subscriber):
                return

            if self.ping_job is not None:
                self.ping_job.schedule_removal()
                self.bot.logger.info("Unset old ping job")
                await self.bot.reply_with_warn_on_failure(ctx, "Unset old ping job")

            ping_time = int(ping_time)
            now = time()

            self.ping_job = await ctx.job_queue.run_repeating(now, self._send_ping, ctx, ping_time)

            await self.bot.reply_with_warn_on_failure(ctx, f"Ping set every {ping_time} seconds")
            self.bot.logger.info(f"Ping set every {ping_time} seconds")
        except Exception as e:
            self.bot.logger.error(e, exc_info=True)
            try:
                await self.bot.reply_with_warn_on_failure(ctx, "Failed set ping")
            except Exception as e:
                self.bot.logger.error(e, exc_info=True)
        # finally:
        #     raise StopPropagation

class UnsetPing(Command):
    def __init__(self, bot: BotAnswers) -> None:
        super().__init__()
        self.bot = bot

    @triggered(CommandRegex.unset_ping)
    async def unset_ping(self, ctx: ChatContext) -> None:
        try:
            if not await self.is_user_admin(ctx, AdminCommandStrings.lift_ban_subscriber):
                return

            if self.ping_job is None:
                await ctx.message.reply("Cannot unset because ping was not set!")
                return

            self.ping_job.schedule_removal()
            self.ping_job = None
            await ctx.message.reply("Ping unset!")
        except Exception as e:
            self.bot.logger.error(e, exc_info=True)
            try:
                await self.bot.reply_with_warn_on_failure(ctx, "Failed to unset ping")
            except Exception as e:
                self.bot.logger.error(e, exc_info=True)
        # finally:
        #     raise StopPropagation

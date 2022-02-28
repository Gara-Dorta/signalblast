from asyncio import gather
from typing import Optional
from semaphore import ChatContext, StopPropagation, Job
from logging import Logger
from time import time

from admin import Admin
from users import Users
from bot_commands import CommandRegex, AdminCommandStrings, PublicCommandStrings
from message_handler import MessageHandler
from utils import get_code_data_path


class BotAnswers():
    subscribers_data_path = get_code_data_path() / 'subscribers.txt'
    banned_users_data_path = get_code_data_path() / 'banned_users.txt'

    subscribers_phone_data_path = get_code_data_path() / 'subscribers_phone.txt'
    banned_users_phone_data_path = get_code_data_path() / 'banned_users_phone.txt'

    def __init__(self) -> None:
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
        self.subscribers_phone: Users = None
        self.banned_users_phone: Users = None
        self.ping_job: Job = None

    @classmethod
    async def create(cls, logger: Logger, admin_pass: Optional[str], expiration_time: Optional[int]) -> 'BotAnswers':
        self = BotAnswers()
        self.subscribers = await Users.load_from_file(self.subscribers_data_path)
        self.banned_users = await Users.load_from_file(self.banned_users_data_path)

        self.subscribers_phone = await Users.load_from_file(self.subscribers_phone_data_path)
        self.banned_users_phone = await Users.load_from_file(self.banned_users_phone_data_path)

        self.admin = await Admin.load_from_file(admin_pass)
        self.message_handler = MessageHandler()

        self.help_message = self.message_handler.compose_help_message(is_help=True)
        self.wrong_command_message = self.message_handler.compose_help_message(is_help=False)
        self.admin_help_message = self.message_handler.compose_help_message(add_admin_commands=True)
        self.admin_wrong_command_message = self.message_handler.compose_help_message(add_admin_commands=True,
                                                                                     is_help=False)

        self.must_subscribe_message = self.message_handler.compose_must_subscribe_message()

        self.expiration_time = expiration_time

        self.logger = logger
        self.logger.debug('BotAnswers is initialised')
        return self

    async def reply_with_warn_on_failure(self, ctx: ChatContext, message: str) -> bool:
        if await ctx.message.reply(message):
            return True
        else:
            self.logger.warning(f"Could not send message to {ctx.message.source.uuid}")
            return False

    async def subscribe(self, ctx: ChatContext) -> None:
        try:
            subscriber_uuid = ctx.message.source.uuid
            if subscriber_uuid in self.subscribers:
                await self.reply_with_warn_on_failure(ctx, "Already subscribed!")
                self.logger.info("Already subscribed!")
                return

            if subscriber_uuid in self.banned_users:
                await self.reply_with_warn_on_failure(ctx, "This number is not allowed to subscribe")
                self.logger.info(f"{subscriber_uuid} was not allowed to subscribe")
                return

            await self.subscribers.add(subscriber_uuid)
            await self.subscribers_phone.add(ctx.message.source.number)
            await self.reply_with_warn_on_failure(ctx, "Subscription successful!")
            if self.expiration_time is not None:
                await ctx.bot.set_expiration(subscriber_uuid, self.expiration_time)
            self.logger.info(f"{subscriber_uuid} subscribed")
        except Exception as e:
            self.logger.error(e, exc_info=True)
            try:
                await self.reply_with_warn_on_failure(ctx, "Could not subscribe!")
            except Exception as e:
                self.logger.error(e, exc_info=True)
        finally:
            raise StopPropagation

    async def unsubscribe(self, ctx: ChatContext) -> None:
        try:
            subscriber_uuid = ctx.message.source.uuid

            if subscriber_uuid not in self.subscribers:
                await self.reply_with_warn_on_failure(ctx, "Not subscribed!")
                self.logger.info(f"{subscriber_uuid} tried to unsubscribe but they are not subscribed")
                return

            await self.subscribers.remove(subscriber_uuid)
            await self.subscribers_phone.remove(ctx.message.source.number)
            await self.reply_with_warn_on_failure(ctx, "Successfully unsubscribed!")
            self.logger.info(f"{subscriber_uuid} unsubscribed")
        except Exception as e:
            self.logger.error(e, exc_info=True)
            try:
                await self.reply_with_warn_on_failure(ctx, "Could not unsubscribe!")
            except Exception as e:
                self.logger.error(e, exc_info=True)
        finally:
            raise StopPropagation

    async def broadcast(self, ctx: ChatContext) -> None:
        num_broadcasts = 0
        num_subscribers = -1

        try:
            subscriber_uuid = ctx.message.source.uuid
            if subscriber_uuid in self.banned_users:
                await ctx.bot.send_message(subscriber_uuid, "This number is not allowed to broadcast messages")
                self.logger.info(f"{subscriber_uuid} tried to broadcast but they are banned")
                return

            if subscriber_uuid not in self.subscribers:
                await ctx.bot.send_message(subscriber_uuid, self.must_subscribe_message)
                self.logger.info(f"{subscriber_uuid} tried to broadcast but they are not subscribed")
                return

            num_subscribers = len(self.subscribers)

            await ctx.message.mark_read()
            message = self.message_handler.remove_command_from_message(ctx.message.get_body(),
                                                                       PublicCommandStrings.broadcast)
            attachments = self.message_handler.prepare_attachments(ctx.message.data_message.attachments)

            if message is None and attachments is None:
                return

            # Broadcast message to all subscribers.
            send_tasks = [None] * len(self.subscribers)

            for i, subscriber in enumerate(self.subscribers):
                send_tasks[i] = ctx.bot.send_message(subscriber, message, attachments=attachments)

            send_task_results = await gather(*send_tasks)

            for send_task_result in send_task_results:
                if send_task_result:
                    num_broadcasts += 1
                    self.logger.info(f"Message successfully sent to {subscriber}")
                else:
                    self.logger.warning(f"Could not send message to {subscriber}")
                    await self.subscribers.remove(ctx.message.source.uuid)
                    await self.subscribers_phone.remove(ctx.message.source.number)

            self.message_handler.delete_attachments(attachments)
        except Exception as e:
            self.logger.error(e, exc_info=True)
            try:
                error_str = "Something went wrong when sending the message"
                if num_broadcasts == num_subscribers:
                    error_str += ", but it was sent to everybody"
                error_str += ", please contact the admin if the problem persists"
                await self.reply_with_warn_on_failure(ctx, error_str)
            except Exception as e:
                self.logger.error(e, exc_info=True)
        finally:
            raise StopPropagation

    def _get_help_message(self, input_message, subscriber_uuid):
        if input_message.startswith(PublicCommandStrings.help):
            is_wrong_command = False
        else:
            is_wrong_command = True

        if subscriber_uuid != self.admin.admin_id:
            if is_wrong_command:
                return self.wrong_command_message
            else:
                return self.help_message
        else:
            if is_wrong_command:
                return self.admin_wrong_command_message
            else:
                return self.admin_help_message

    async def display_help(self, ctx: ChatContext) -> None:
        try:
            subscriber_uuid = ctx.message.source.uuid
            message = ctx.message.get_body()
            help_message = self._get_help_message(message, subscriber_uuid)

            for regex in CommandRegex:
                if regex.search(message) is not None:
                    return

            if message == '':
                if ctx.message.data_message.attachments == []:
                    self.logger.info(f"Received reaction, sticker or similar from {subscriber_uuid}")
                    return

                # Only attachment, assume the user wants to forward that
                self.logger.info(f"Received a file from {subscriber_uuid}, broadcasting!")
                await self.broadcast(ctx)
                return

            await self.reply_with_warn_on_failure(ctx, help_message)
            self.logger.info(f"Sent help message to {subscriber_uuid}")
        except Exception as e:
            self.logger.error(e, exc_info=True)

    async def add_admin(self, ctx: ChatContext) -> None:
        try:
            subscriber_uuid = ctx.message.source.uuid
            password = self.message_handler.remove_command_from_message(ctx.message.get_body(),
                                                                        AdminCommandStrings.add_admin)

            previous_admin = self.admin.admin_id
            if await self.admin.add(subscriber_uuid, password):
                await self.reply_with_warn_on_failure(ctx, 'You have been added as admin!')
                if previous_admin is not None and subscriber_uuid != previous_admin:
                    msg_to_admin = self.message_handler.compose_message_to_admin('You are no longer an admin!',
                                                                                 subscriber_uuid)
                    await ctx.bot.send_message(previous_admin, msg_to_admin)
                log_message = f"Previous admin was {previous_admin}, new admin is {subscriber_uuid}"
                self.logger.info(log_message)
            else:
                await self.reply_with_warn_on_failure(ctx, 'Adding failed, admin password is incorrect!')
                if previous_admin is not None:
                    msg_to_admin = self.message_handler.compose_message_to_admin('Tried to be added as admin',
                                                                                 subscriber_uuid)
                    await ctx.bot.send_message(previous_admin, msg_to_admin)
                self.logger.warning(f"{subscriber_uuid} failed password check for add_admin")
        except Exception as e:
            self.logger.error(e, exc_info=True)
        finally:
            raise StopPropagation

    async def remove_admin(self, ctx: ChatContext) -> None:
        try:
            subscriber_uuid = ctx.message.source.uuid
            password = self.message_handler.remove_command_from_message(ctx.message.get_body(),
                                                                        AdminCommandStrings.remove_admin)

            previous_admin = self.admin.admin_id
            if await self.admin.remove(password):
                await self.reply_with_warn_on_failure(ctx, 'Admin has been removed!')
                if previous_admin is not None and subscriber_uuid != previous_admin:
                    msg_to_admin = self.message_handler.compose_message_to_admin('You are no longer an admin!',
                                                                                 subscriber_uuid)
                    await ctx.bot.send_message(previous_admin, msg_to_admin)
                self.logger.info(f"{previous_admin} is no longer an admin")
            else:
                await self.reply_with_warn_on_failure(ctx, 'Removing failed: admin password is incorrect!')
                if previous_admin is not None:
                    msg_to_admin = self.message_handler.compose_message_to_admin('Tried to remove you as admin',
                                                                                 subscriber_uuid)
                    await ctx.bot.send_message(previous_admin, msg_to_admin)
                self.logger.warning(f"Failed password check for remove_admin {subscriber_uuid}")
        except Exception as e:
            self.logger.error(e, exc_info=True)
        finally:
            raise StopPropagation

    async def msg_to_admin(self, ctx: ChatContext) -> None:
        try:
            subscriber_uuid = ctx.message.source.uuid
            message = self.message_handler.remove_command_from_message(ctx.message.get_body(),
                                                                       PublicCommandStrings.msg_to_admin)

            if self.admin.admin_id is None:
                await self.reply_with_warn_on_failure(ctx, "I'm sorry but there are no admins to contact!")
                self.logger.info(f"Tried to contact an admin but there is none! {subscriber_uuid}")
                return

            if subscriber_uuid in self.banned_users:
                await self.reply_with_warn_on_failure(ctx, "You are not allowed to contact the admin!")
                self.logger.info(f"Banned user {subscriber_uuid} tried to contact admin")
                return

            msg_to_admin = self.message_handler.compose_message_to_admin('Sent you message:\n', subscriber_uuid)
            msg_to_admin += message
            attachments = self.message_handler.prepare_attachments(ctx.message.data_message.attachments)
            await ctx.bot.send_message(self.admin.admin_id, msg_to_admin, attachments=attachments)
            self.logger.info(f"Sent message from {subscriber_uuid} to admin {self.admin.admin_id}")
        except Exception as e:
            self.logger.error(e, exc_info=True)
            try:
                await self.reply_with_warn_on_failure(ctx, "Failed to send the message to the admin!")
            except Exception as e:
                self.logger.error(e, exc_info=True)
        finally:
            raise StopPropagation

    async def is_user_admin(self, ctx: ChatContext, command: str) -> bool:
        subscriber_uuid = ctx.message.source.uuid
        if self.admin.admin_id is None:
            await self.reply_with_warn_on_failure(ctx, "I'm sorry but there are no admins")
            self.logger.info(f"Tried to {command} but there are no admins! {subscriber_uuid}")
            return False

        if self.admin.admin_id != subscriber_uuid:
            await self.reply_with_warn_on_failure(ctx, "I'm sorry but you are not an admin")
            msg_to_admin = self.message_handler.compose_message_to_admin(f'Tried to {command}', subscriber_uuid)
            await ctx.bot.send_message(self.admin.admin_id, msg_to_admin)
            self.logger.info(f"{subscriber_uuid} tried to {command} but admin is {self.admin.admin_id}")
            return False

        return True

    async def msg_from_admin(self, ctx: ChatContext) -> None:
        try:
            message = self.message_handler.remove_command_from_message(ctx.message.get_body(),
                                                                       AdminCommandStrings.msg_from_admin)

            if not await self.is_user_admin(ctx, AdminCommandStrings.ban_subscriber):
                return

            user_id, message = message.split(' ', 1)
            message = 'Admin: ' + message
            attachments = self.message_handler.prepare_attachments(ctx.message.data_message.attachments)

            await ctx.bot.send_message(user_id, message, attachments=attachments)
            self.logger.info(f"Sent message from admin {self.admin.admin_id} to user {user_id}")
        except Exception as e:
            self.logger.error(e, exc_info=True)
            try:
                await self.reply_with_warn_on_failure(ctx, "Failed to send the message to the user!")
            except Exception as e:
                self.logger.error(e, exc_info=True)
        finally:
            raise StopPropagation

    async def ban_user(self, ctx: ChatContext) -> None:
        try:
            user_id = self.message_handler.remove_command_from_message(ctx.message.get_body(),
                                                                       AdminCommandStrings.ban_subscriber)

            if not await self.is_user_admin(ctx, AdminCommandStrings.ban_subscriber):
                return

            if user_id in self.subscribers:
                await self.subscribers.remove(user_id)
                await self.subscribers_phone.remove(ctx.message.source.number)
            await self.banned_users.add(user_id)
            await self.banned_users_phone.add(ctx.message.source.number)

            await ctx.bot.send_message(user_id, 'You have been banned')
            await self.reply_with_warn_on_failure(ctx, "Successfully banned user")

            self.logger.info(f"Banned user {user_id}")
        except Exception as e:
            self.logger.error(e, exc_info=True)
            try:
                await self.reply_with_warn_on_failure(ctx, "Failed to ban user")
            except Exception as e:
                self.logger.error(e, exc_info=True)
        finally:
            raise StopPropagation

    async def lift_ban_user(self, ctx: ChatContext) -> None:
        try:
            user_id = self.message_handler.remove_command_from_message(ctx.message.get_body(),
                                                                       AdminCommandStrings.lift_ban_subscriber)

            if not await self.is_user_admin(ctx, AdminCommandStrings.lift_ban_subscriber):
                return

            if user_id in self.banned_users:
                await self.banned_users.remove(user_id)
                await self.banned_users_phone.remove(ctx.message.source.number)
            else:
                await self.reply_with_warn_on_failure(ctx, "Could not lift the ban because the user was not banned")
                self.logger.info(f"Could not lift the ban of {user_id} because the user was not banned")
                return

            await ctx.bot.send_message(user_id, 'You have banned have been lifted, try subscribing again')
            await self.reply_with_warn_on_failure(ctx, "Successfully lifted the ban on the user")

            self.logger.info(f"Lifted the ban on user {user_id}")
        except Exception as e:
            self.logger.error(e, exc_info=True)
            try:
                await self.reply_with_warn_on_failure(ctx, "Failed lift the ban on the user")
            except Exception as e:
                self.logger.error(e, exc_info=True)
        finally:
            raise StopPropagation

    async def _send_ping(self, ctx: ChatContext) -> None:
        try:
            await self.reply_with_warn_on_failure(ctx, "Ping")
        except Exception as e:
            self.logger.error(e, exc_info=True)
            try:
                await self.reply_with_warn_on_failure(ctx, "Failed to send ping")
            except Exception as e:
                self.logger.error(e, exc_info=True)

    async def set_ping(self, ctx: ChatContext) -> None:
        try:
            ping_time = self.message_handler.remove_command_from_message(ctx.message.get_body(),
                                                                       AdminCommandStrings.set_ping)

            if not await self.is_user_admin(ctx, AdminCommandStrings.lift_ban_subscriber):
                return

            if self.ping_job is not None:
                self.ping_job.schedule_removal()
                self.logger.info("Unset old ping job")
                await self.reply_with_warn_on_failure(ctx, "Unset old ping job")

            ping_time = int(ping_time)
            now = time()

            self.ping_job = await ctx.job_queue.run_repeating(now, self._send_ping, ctx, ping_time)

            await self.reply_with_warn_on_failure(ctx, f"Ping set every {ping_time} seconds")
            self.logger.info(f"Ping set every {ping_time} seconds")
        except Exception as e:
            self.logger.error(e, exc_info=True)
            try:
                await self.reply_with_warn_on_failure(ctx, "Failed set ping")
            except Exception as e:
                self.logger.error(e, exc_info=True)
        finally:
            raise StopPropagation

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
            self.logger.error(e, exc_info=True)
            try:
                await self.reply_with_warn_on_failure(ctx, "Failed to unset ping")
            except Exception as e:
                self.logger.error(e, exc_info=True)
        finally:
            raise StopPropagation

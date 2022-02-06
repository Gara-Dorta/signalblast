from typing import Optional
from semaphore import ChatContext
from logging import Logger

from admin import Admin
from users import Users
from bot_commands import CommandRegex, AdminCommandStrings, PublicCommandStrings
from message_handler import MessageHandler


class BotAnswers():
    subscribers_data_path = './data/subscribers.txt'
    banned_users_data_path = './data/banned_users.txt'

    @classmethod
    async def create(cls, logger: Logger, admin_pass: Optional[str]) -> None:
        self = BotAnswers()
        self.subscribers = await Users.load_from_file(self.subscribers_data_path)
        self.banned_users = await Users.load_from_file(self.banned_users_data_path)

        self.admin = await Admin.load_from_file(admin_pass)
        self.message_handler = MessageHandler()

        self.help_message = self.message_handler.compose_help_message()
        self.admin_help_message = self.message_handler.compose_help_message(add_admin_commands=True)
        self.must_subscribe_message = self.message_handler.compose_must_subscribe_message()

        self.logger = logger
        self.logger.debug('BotAnswers is initialised')
        return self

    async def reply_with_warn_on_failure(self, ctx, message) -> bool:
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
            else:
                if subscriber_uuid in self.banned_users:
                    await self.reply_with_warn_on_failure(ctx, "This number is not allowed to subscribe")
                    self.logger.info(f"{subscriber_uuid} was not allowed to subscribe")
                    return

                await self.subscribers.add(subscriber_uuid)
                await self.reply_with_warn_on_failure(ctx, "Subscription successful!")
                self.logger.info(f"{subscriber_uuid} subscribed")
        except Exception as e:
            self.logger.error(e, exc_info=True)
            try:
                await self.reply_with_warn_on_failure(ctx, "Could not subscribe!")
            except Exception as e:
                self.logger.error(e, exc_info=True)

    async def unsubscribe(self, ctx: ChatContext) -> None:
        try:
            subscriber_uuid = ctx.message.source.uuid
            if subscriber_uuid in self.subscribers:
                await self.subscribers.remove(subscriber_uuid)
                await self.reply_with_warn_on_failure(ctx, "Successfully unsubscribed!")
                self.logger.info(f"{subscriber_uuid} unsubscribed")
            else:
                await self.reply_with_warn_on_failure(ctx, "Not subscribed!")
                self.logger.info(f"{subscriber_uuid} tried to unsubscribe but they are not subscribed")
        except Exception as e:
            self.logger.error(e, exc_info=True)
            try:
                await self.reply_with_warn_on_failure(ctx, "Could not unsubscribe!")
            except Exception as e:
                self.logger.error(e, exc_info=True)

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
            message = self.message_handler.prepare_broadcast_message(ctx.message.get_body())
            attachments = self.message_handler.prepare_attachments(ctx.message.data_message.attachments)

            if message is None and attachments is None:
                return

            # Broadcast message to all subscribers.
            for subscriber in self.subscribers:
                if await ctx.bot.send_message(subscriber, message, attachments=attachments):
                    num_broadcasts += 1
                    self.logger.info(f"Message successfully sent to {subscriber}")
                else:
                    self.logger.warning(f"Could not send message to {subscriber}")
                    await self.subscribers.remove(ctx.message.source.uuid)
        except Exception as e:
            self.logger.error(e, exc_info=True)
            try:
                error_str = "Something went wrong, could only send the message to "\
                            f"{num_broadcasts} out of {num_subscribers} subscribers"
                await self.reply_with_warn_on_failure(ctx, error_str)
            except Exception as e:
                self.logger.error(e, exc_info=True)

    async def display_help(self, ctx: ChatContext) -> None:
        try:
            subscriber_uuid = ctx.message.source.uuid
            message = ctx.message.get_body()
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
            else:
                if subscriber_uuid != self.admin.admin_id:
                    help_message = self.help_message
                else:
                    help_message = self.admin_help_message
                await self.reply_with_warn_on_failure(ctx, help_message)
                self.logger.info(f"Sent help message to {subscriber_uuid}")
        except Exception as e:
            self.logger.error(e, exc_info=True)

    async def add_admin(self, ctx: ChatContext) -> None:
        try:
            subscriber_uuid = ctx.message.source.uuid
            message = ctx.message.get_body()
            message = message.replace(AdminCommandStrings.add_admin, '', 1).strip()

            previous_admin = self.admin.admin_id
            if await self.admin.add(subscriber_uuid, message):
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

    async def remove_admin(self, ctx: ChatContext) -> None:
        try:
            subscriber_uuid = ctx.message.source.uuid
            message = ctx.message.get_body()
            message = message.replace(AdminCommandStrings.remove_admin, '', 1).strip()

            previous_admin = self.admin.admin_id
            if await self.admin.remove(message):
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

    async def msg_to_admin(self, ctx: ChatContext) -> None:
        try:
            subscriber_uuid = ctx.message.source.uuid
            message = ctx.message.get_body()
            message = message.replace(PublicCommandStrings.msg_to_admin, '', 1).strip()

            if self.admin.admin_id is None:
                await self.reply_with_warn_on_failure(ctx, "I'm sorry but there are no admins to contact!")
                self.logger.info(f"Tried to contact an admin but there is none! {subscriber_uuid}")
            else:
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

    async def msg_from_admin(self, ctx: ChatContext) -> None:
        try:
            subscriber_uuid = ctx.message.source.uuid
            message = ctx.message.get_body()
            message = message.replace(AdminCommandStrings.msg_from_admin, '', 1).strip()

            if self.admin.admin_id is None:
                await self.reply_with_warn_on_failure(ctx, "I'm sorry but there are no admins")
                self.logger.info(f"Tried send a message as admin but there are no admins! {subscriber_uuid}")
                return

            if self.admin.admin_id != subscriber_uuid:
                await self.reply_with_warn_on_failure(ctx, "I'm sorry but you are not an admin")
                msg_to_admin = self.message_handler.compose_message_to_admin('Tried to reply as admin', subscriber_uuid)
                await ctx.bot.send_message(self.admin.admin_id, msg_to_admin)
                self.logger.info(f"{subscriber_uuid} tried send a message as admin but admin is {self.admin.admin_id}")
                return

            user_id, message = message.split(' ', 1)
            message = 'Admin: ' + message
            attachments = self.message_handler.prepare_attachments(ctx.message.data_message.attachments)

            await ctx.bot.send_message(user_id, message, attachments=attachments)
            self.logger.info(f"Sent message from admin {self.admin.admin_id} to user {subscriber_uuid}")
        except Exception as e:
            self.logger.error(e, exc_info=True)
            try:
                await self.reply_with_warn_on_failure(ctx, "Failed to send the message to the user!")
            except Exception as e:
                self.logger.error(e, exc_info=True)

    async def ban_user(self, ctx: ChatContext) -> None:
        try:
            subscriber_uuid = ctx.message.source.uuid
            message = ctx.message.get_body()
            user_id = message.replace(AdminCommandStrings.ban_subscriber, '', 1).strip()

            if self.admin.admin_id is None:
                await self.reply_with_warn_on_failure(ctx, "I'm sorry but there are no admins")
                self.logger.info(f"Tried to ban a user but there are no admins! {subscriber_uuid}")
                return

            if self.admin.admin_id != subscriber_uuid:
                await self.reply_with_warn_on_failure(ctx, "I'm sorry but you are not an admin")
                msg_to_admin = self.message_handler.compose_message_to_admin('Tried to ban a user', subscriber_uuid)
                await ctx.bot.send_message(self.admin.admin_id, msg_to_admin)
                self.logger.info(f"{subscriber_uuid} tried to ban a user but admin is {self.admin.admin_id}")
                return

            if user_id in self.subscribers:
                await self.subscribers.remove(user_id)
            await self.banned_users.add(user_id)

            await ctx.bot.send_message(user_id, 'You have been banned')
            await self.reply_with_warn_on_failure(ctx, "Successfully banned user")

            self.logger.info(f"Banned user {user_id}")
        except Exception as e:
            self.logger.error(e, exc_info=True)
            try:
                await self.reply_with_warn_on_failure(ctx, "Failed to ban user")
            except Exception as e:
                self.logger.error(e, exc_info=True)

    async def lift_ban_user(self, ctx: ChatContext) -> None:
        try:
            subscriber_uuid = ctx.message.source.uuid
            message = ctx.message.get_body()
            user_id = message.replace(AdminCommandStrings.lift_ban_subscriber, '', 1).strip()

            if self.admin.admin_id is None:
                await self.reply_with_warn_on_failure(ctx, "I'm sorry but there are no admins")
                self.logger.info(f"Tried to lift the ban of a user but there are no admins! {subscriber_uuid}")
                return

            if self.admin.admin_id != subscriber_uuid:
                await self.reply_with_warn_on_failure(ctx, "I'm sorry but you are not an admin")
                msg_to_admin = self.message_handler.compose_message_to_admin('Tried to lift ban a user',
                                                                             subscriber_uuid)
                await ctx.bot.send_message(self.admin.admin_id, msg_to_admin)
                self.logger.info(f"{subscriber_uuid} tried to lift ban a user but admin is {self.admin.admin_id}")
                return

            if user_id in self.banned_users:
                await self.banned_users.remove(user_id)
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

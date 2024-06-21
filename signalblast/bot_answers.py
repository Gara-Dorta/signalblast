from asyncio import gather
from typing import Optional, Callable, Union, List
from logging import Logger
from datetime import datetime
from pathlib import Path

from admin import Admin
from users import Users
from bot_commands import CommandRegex, AdminCommandStrings, PublicCommandStrings
from message_handler import MessageHandler
from utils import get_code_data_path
from signalbot import Command, Message #, triggered
from signalbot import Context as ChatContext
from signalbot import SignalBot
import functools
from re import Pattern
from broadcastbot import BroadcasBot

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



class Subscribe(Command):
    def __init__(self, bot: BroadcasBot) -> None:
        super().__init__()
        self.broadcastbot = bot

    async def subscribe(self, ctx: ChatContext, verbose: bool = False) -> None:
        try:
            subscriber_uuid = ctx.message.source_uuid
            if subscriber_uuid in self.broadcastbot.subscribers:
                if verbose:
                    await self.broadcastbot.reply_with_warn_on_failure(ctx, "Already subscribed!")
                    self.broadcastbot.logger.info("Already subscribed!")
                return

            if subscriber_uuid in self.broadcastbot.banned_users:
                if verbose:
                    await self.broadcastbot.reply_with_warn_on_failure(ctx, "This number is not allowed to subscribe")
                    self.broadcastbot.logger.info(f"{subscriber_uuid} was not allowed to subscribe")
                return

            await self.broadcastbot.subscribers.add(subscriber_uuid, ctx.message.source_number)
            if verbose:
                await self.broadcastbot.reply_with_warn_on_failure(ctx, "Subscription successful!")
            # if self.broadcastbot.expiration_time is not None:
            #     await ctx.bot.set_expiration(subscriber_uuid, self.broadcastbot.expiration_time)
            self.broadcastbot.logger.info(f"{subscriber_uuid} subscribed")
        except Exception as e:
            self.broadcastbot.logger.error(e, exc_info=True)
            try:
                await self.broadcastbot.reply_with_warn_on_failure(ctx, "Could not subscribe!")
            except Exception as e:
                self.broadcastbot.logger.error(e, exc_info=True)

    @triggered(CommandRegex.subscribe)
    async def handle(self, ctx: ChatContext) -> None:
        await Subscribe.subscribe(self, ctx, verbose=True)

class Unsubscribe(Command):
    def __init__(self, bot: BroadcasBot) -> None:
        super().__init__()
        self.broadcastbot = bot

    @triggered(CommandRegex.unsubscribe)
    async def handle(self, ctx: ChatContext) -> None:
        try:
            subscriber_uuid = ctx.message.source_uuid

            if subscriber_uuid not in self.broadcastbot.subscribers:
                await self.broadcastbot.reply_with_warn_on_failure(ctx, "Not subscribed!")
                self.broadcastbot.logger.info(f"{subscriber_uuid} tried to unsubscribe but they are not subscribed")
                return

            await self.broadcastbot.subscribers.remove(subscriber_uuid)
            await self.broadcastbot.reply_with_warn_on_failure(ctx, "Successfully unsubscribed!")
            self.broadcastbot.logger.info(f"{subscriber_uuid} unsubscribed")
        except Exception as e:
            self.broadcastbot.logger.error(e, exc_info=True)
            try:
                await self.broadcastbot.reply_with_warn_on_failure(ctx, "Could not unsubscribe!")
            except Exception as e:
                self.broadcastbot.logger.error(e, exc_info=True)
        # finally:
        #     raise StopPropagation

class Broadcast(Command):
    def __init__(self, bot: BroadcasBot) -> None:
        super().__init__()
        self.broadcastbot = bot

    def is_valid_command(self, message: str, invalid_command: Pattern) -> bool:
            regex: Pattern
            for regex in CommandRegex:
                if regex != invalid_command and regex.search(message) is not None:
                    return True                
            return False

    @staticmethod
    async def broadcast(bot: BroadcasBot, ctx: ChatContext) -> None:
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
                send_tasks[i] = bot.send(subscriber, message, base64_attachments=attachments)
                                                    #  link_previews=link_previews)

            send_task_results = await gather(*send_tasks)

            for send_task_result in send_task_results:
                if isinstance(send_task_result, str):
                    num_broadcasts += 1
                    bot.logger.info(f"Message successfully sent to {subscriber}")
                else:
                    bot.logger.warning(f"Could not send message to {subscriber}")
                    await bot.subscribers.remove(ctx.message.source_uuid)

            attachments_filenames = bot.message_handler.empty_list_to_none(ctx.message.attachments_filenames)
            bot.message_handler.delete_attachments(attachments_filenames, link_previews=None)

            await bot.reply_with_warn_on_failure(ctx, f"Message sent to {num_broadcasts - 1} people")
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

    async def handle(self, ctx: ChatContext) -> None:
        message = ctx.message.text
        subscriber_uuid = ctx.message.source_uuid
        if message == None:
            if ctx.message.base64_attachments == []:
                self.broadcastbot.logger.info(f"Received reaction, sticker or similar from {subscriber_uuid}")
                return

            # Only attachment, assume the user wants to forward that
            self.broadcastbot.logger.info(f"Received a file from {subscriber_uuid}, broadcasting!")
            await Broadcast.broadcast(self.broadcastbot, ctx)
            return

        if self.is_valid_command(message, invalid_command=CommandRegex.broadcast):
            return
        
        if subscriber_uuid not in self.broadcastbot.subscribers:
            await Subscribe(bot=self.broadcastbot).subscribe(ctx)

        # By default broadcast all the messages
        await Broadcast.broadcast(self.broadcastbot, ctx)



class DisplayHelp(Command):
    def __init__(self, bot: BroadcasBot) -> None:
        super().__init__()
        self.broadcastbot = bot

    def _get_help_message(self, input_message: str, subscriber_uuid: str) -> str:
        if input_message.startswith(PublicCommandStrings.help):
            is_wrong_command = False
        else:
            is_wrong_command = True

        if subscriber_uuid != self.broadcastbot.admin.admin_id:
            if is_wrong_command:
                return self.broadcastbot.wrong_command_message
            else:
                return self.broadcastbot.help_message
        else:
            if is_wrong_command:
                return self.broadcastbot.admin_wrong_command_message
            else:
                return self.broadcastbot.admin_help_message

    @triggered(CommandRegex.help)
    async def handle(self, ctx: ChatContext) -> None:
        try:
            subscriber_uuid = ctx.message.source_uuid
            message = ctx.message.text
            
            help_message = self._get_help_message(message, subscriber_uuid)

            await self.broadcastbot.reply_with_warn_on_failure(ctx, help_message)
            self.broadcastbot.logger.info(f"Sent help message to {subscriber_uuid}")
        except Exception as e:
            # if isinstance(e, StopPropagation):
            #     raise
            self.broadcastbot.logger.error(e, exc_info=True)

class AddAdmin(Command):
    def __init__(self, bot: BroadcasBot) -> None:
        super().__init__()
        self.broadcastbot = bot

    @triggered(CommandRegex.add_admin)
    async def handle(self, ctx: ChatContext) -> None:
        try:
            subscriber_uuid = ctx.message.source_uuid
            password = self.broadcastbot.message_handler.remove_command_from_message(ctx.message.text,
                                                                        AdminCommandStrings.add_admin)

            previous_admin = self.broadcastbot.admin.admin_id
            if await self.broadcastbot.admin.add(subscriber_uuid, password):
                await self.broadcastbot.reply_with_warn_on_failure(ctx, 'You have been added as admin!')
                if previous_admin is not None and subscriber_uuid != previous_admin:
                    msg_to_admin = self.broadcastbot.message_handler.compose_message_to_admin('You are no longer an admin!',
                                                                                 subscriber_uuid)
                    await self.broadcastbot.send(previous_admin, msg_to_admin)
                log_message = f"Previous admin was {previous_admin}, new admin is {subscriber_uuid}"
                self.broadcastbot.logger.info(log_message)
            else:
                await self.broadcastbot.reply_with_warn_on_failure(ctx, 'Adding failed, admin password is incorrect!')
                if previous_admin is not None:
                    msg_to_admin = self.broadcastbot.message_handler.compose_message_to_admin('Tried to be added as admin',
                                                                                 subscriber_uuid)
                    await self.broadcastbot.send(previous_admin, msg_to_admin)
                self.broadcastbot.logger.warning(f"{subscriber_uuid} failed password check for add_admin")
        except Exception as e:
            self.broadcastbot.logger.error(e, exc_info=True)
        # finally:
        #     raise StopPropagation
        
class RemoveAdmin(Command):
    def __init__(self, bot: BroadcasBot) -> None:
        super().__init__()
        self.broadcastbot = bot

    @triggered(CommandRegex.remove_admin)
    async def handle(self, ctx: ChatContext) -> None:
        try:
            subscriber_uuid = ctx.message.source_uuid
            password = self.broadcastbot.message_handler.remove_command_from_message(ctx.message.get_body(),
                                                                        AdminCommandStrings.remove_admin)

            previous_admin = self.broadcastbot.admin.admin_id
            if await self.broadcastbot.admin.remove(password):
                await self.broadcastbot.reply_with_warn_on_failure(ctx, 'Admin has been removed!')
                if previous_admin is not None and subscriber_uuid != previous_admin:
                    msg_to_admin = self.broadcastbot.message_handler.compose_message_to_admin('You are no longer an admin!',
                                                                                 subscriber_uuid)
                    await self.broadcastbot.send(previous_admin, msg_to_admin)
                self.broadcastbot.logger.info(f"{previous_admin} is no longer an admin")
            else:
                await self.broadcastbot.reply_with_warn_on_failure(ctx, 'Removing failed: admin password is incorrect!')
                if previous_admin is not None:
                    msg_to_admin = self.broadcastbot.message_handler.compose_message_to_admin('Tried to remove you as admin',
                                                                                 subscriber_uuid)
                    await self.broadcastbot.send(previous_admin, msg_to_admin)
                self.broadcastbot.logger.warning(f"Failed password check for remove_admin {subscriber_uuid}")
        except Exception as e:
            self.broadcastbot.logger.error(e, exc_info=True)
        # finally:
        #     raise StopPropagation

class MessageToAdmin(Command):
    def __init__(self, bot: BroadcasBot) -> None:
        super().__init__()
        self.broadcastbot = bot

    @triggered(CommandRegex.msg_to_admin)
    async def handle(self, ctx: ChatContext) -> None:
        try:
            subscriber_uuid = ctx.message.source_uuid
            message = self.broadcastbot.message_handler.remove_command_from_message(ctx.message.get_body(),
                                                                       PublicCommandStrings.msg_to_admin)

            if self.broadcastbot.admin.admin_id is None:
                await self.broadcastbot.reply_with_warn_on_failure(ctx, "I'm sorry but there are no admins to contact!")
                self.broadcastbot.logger.info(f"Tried to contact an admin but there is none! {subscriber_uuid}")
                return

            if subscriber_uuid in self.broadcastbot.banned_users:
                await self.broadcastbot.reply_with_warn_on_failure(ctx, "You are not allowed to contact the admin!")
                self.broadcastbot.logger.info(f"Banned user {subscriber_uuid} tried to contact admin")
                return

            msg_to_admin = self.broadcastbot.message_handler.compose_message_to_admin('Sent you message:\n', subscriber_uuid)
            msg_to_admin += message
            attachments = self.broadcastbot.message_handler.empty_list_to_none(ctx.message.data_message.attachments)
            await self.broadcastbot.send(self.broadcastbot.admin.admin_id, msg_to_admin, attachments=attachments)
            self.broadcastbot.logger.info(f"Sent message from {subscriber_uuid} to admin {self.broadcastbot.admin.admin_id}")
        except Exception as e:
            self.broadcastbot.logger.error(e, exc_info=True)
            try:
                await self.broadcastbot.reply_with_warn_on_failure(ctx, "Failed to send the message to the admin!")
            except Exception as e:
                self.broadcastbot.logger.error(e, exc_info=True)
        # finally:
        #     raise StopPropagation



class MessageFromAdmin(Command):
    def __init__(self, bot: BroadcasBot) -> None:
        super().__init__()
        self.broadcastbot = bot

    @triggered(CommandRegex.msg_from_admin)
    async def handle(self, ctx: ChatContext) -> None:
        try:
            message = self.broadcastbot.message_handler.remove_command_from_message(ctx.message.get_body(),
                                                                       AdminCommandStrings.msg_from_admin)

            if not await self.broadcastbot.is_user_admin(ctx, AdminCommandStrings.msg_from_admin):
                return

            user_id, message = message.split(' ', 1)

            if user_id not in self.broadcastbot.subscribers:
                if ' ' in message:
                    confirmation, message = message.split(' ', 1)
                else:
                    confirmation = None
                if confirmation != '!force':
                    warn_message = "User is not in subscribers list, use !reply <uuid> !force to message them"
                    await self.broadcastbot.reply_with_warn_on_failure(ctx, warn_message)
                    return

            message = 'Admin: ' + message
            attachments = self.broadcastbot.message_handler.empty_list_to_none(ctx.message.data_message.attachments)

            await self.broadcastbot.send(user_id, message, attachments=attachments)
            self.broadcastbot.logger.info(f"Sent message from admin {self.broadcastbot.admin.admin_id} to user {user_id}")
        except Exception as e:
            self.broadcastbot.logger.error(e, exc_info=True)
            try:
                await self.broadcastbot.reply_with_warn_on_failure(ctx, "Failed to send the message to the user!")
            except Exception as e:
                self.broadcastbot.logger.error(e, exc_info=True)
        # finally:
        #     raise StopPropagation

class BanSubscriber(Command):
    def __init__(self, bot: BroadcasBot) -> None:
        super().__init__()
        self.broadcastbot = bot

    @triggered(CommandRegex.ban_subscriber)
    async def handle(self, ctx: ChatContext) -> None:
        try:
            user_id = self.broadcastbot.message_handler.remove_command_from_message(ctx.message.text,
                                                                       AdminCommandStrings.ban_subscriber)

            if not await self.broadcastbot.is_user_admin(ctx, AdminCommandStrings.ban_subscriber):
                return

            if user_id in self.broadcastbot.subscribers:
                await self.broadcastbot.subscribers.remove(user_id)

            user_phonenumber = self.broadcastbot.subscribers.get_phone_number(user_id)
            await self.broadcastbot.banned_users.add(user_id, user_phonenumber)

            await self.broadcastbot.send(user_id, 'You have been banned')
            await self.broadcastbot.reply_with_warn_on_failure(ctx, "Successfully banned user")

            self.broadcastbot.logger.info(f"Banned user {user_id}")
        except Exception as e:
            self.broadcastbot.logger.error(e, exc_info=True)
            try:
                await self.broadcastbot.reply_with_warn_on_failure(ctx, "Failed to ban user")
            except Exception as e:
                self.broadcastbot.logger.error(e, exc_info=True)
        # finally:
        #     raise StopPropagation

class LiftBanSubscriber(Command):
    def __init__(self, bot: BroadcasBot) -> None:
        super().__init__()
        self.broadcastbot = bot

    @triggered(CommandRegex.lift_ban_subscriber)
    async def handle(self, ctx: ChatContext) -> None:
        try:
            user_id = self.broadcastbot.message_handler.remove_command_from_message(ctx.message.text,
                                                                       AdminCommandStrings.lift_ban_subscriber)

            if not await self.broadcastbot.is_user_admin(ctx, AdminCommandStrings.lift_ban_subscriber):
                return

            if user_id in self.broadcastbot.banned_users:
                await self.broadcastbot.banned_users.remove(user_id)
            else:
                await self.broadcastbot.reply_with_warn_on_failure(ctx, "Could not lift the ban because the user was not banned")
                self.broadcastbot.logger.info(f"Could not lift the ban of {user_id} because the user was not banned")
                return

            await self.broadcastbot.send(user_id, 'You have banned have been lifted, try subscribing again')
            await self.broadcastbot.reply_with_warn_on_failure(ctx, "Successfully lifted the ban on the user")

            self.broadcastbot.logger.info(f"Lifted the ban on user {user_id}")
        except Exception as e:
            self.broadcastbot.logger.error(e, exc_info=True)
            try:
                await self.broadcastbot.reply_with_warn_on_failure(ctx, "Failed lift the ban on the user")
            except Exception as e:
                self.broadcastbot.logger.error(e, exc_info=True)
        # finally:
        #     raise StopPropagation



class SetPing(Command):
    def __init__(self, bot: BroadcasBot) -> None:
        super().__init__()
        self.broadcastbot = bot

    async def _send_ping(self, ctx: ChatContext) -> None:
        try:
            await self.broadcastbot.reply_with_warn_on_failure(ctx, "Ping")
        except Exception as e:
            self.broadcastbot.logger.error(e, exc_info=True)
            try:
                await self.broadcastbot.reply_with_warn_on_failure(ctx, "Failed to send ping")
            except Exception as e:
                self.broadcastbot.logger.error(e, exc_info=True)

    @triggered(CommandRegex.set_ping)
    async def handle(self, ctx: ChatContext) -> None:
        try:
            ping_time = self.broadcastbot.message_handler.remove_command_from_message(ctx.message.text,
                                                                       AdminCommandStrings.set_ping)

            if not await self.broadcastbot.is_user_admin(ctx, AdminCommandStrings.set_ping):
                return

            if self.broadcastbot.ping_job is not None:
                self.broadcastbot.scheduler.remove_job(self.broadcastbot.ping_job.id)
                self.broadcastbot.logger.info("Unset old ping job")
                await self.broadcastbot.reply_with_warn_on_failure(ctx, "Unset old ping job")

            self.broadcastbot.ping_job = self.broadcastbot.scheduler.add_job(self._send_ping, 'interval', seconds=int(ping_time), args=[ctx])

            await self.broadcastbot.reply_with_warn_on_failure(ctx, f"Ping set every {ping_time} seconds")
            self.broadcastbot.logger.info(f"Ping set every {ping_time} seconds")
        except Exception as e:
            self.broadcastbot.logger.error(e, exc_info=True)
            try:
                await self.broadcastbot.reply_with_warn_on_failure(ctx, "Failed set ping")
            except Exception as e:
                self.broadcastbot.logger.error(e, exc_info=True)
        # finally:
        #     raise StopPropagation

class UnsetPing(Command):
    def __init__(self, bot: BroadcasBot) -> None:
        super().__init__()
        self.broadcastbot = bot

    @triggered(CommandRegex.unset_ping)
    async def handle(self, ctx: ChatContext) -> None:
        try:
            if not await self.broadcastbot.is_user_admin(ctx, AdminCommandStrings.unset_ping):
                return

            if self.broadcastbot.ping_job is None:
                await ctx.reply("Cannot unset because ping was not set!")
                return

            self.broadcastbot.scheduler.remove_job(self.broadcastbot.ping_job.id)
            self.broadcastbot.ping_job = None
            await ctx.reply("Ping unset!")
        except Exception as e:
            self.broadcastbot.logger.error(e, exc_info=True)
            try:
                await self.broadcastbot.reply_with_warn_on_failure(ctx, "Failed to unset ping")
            except Exception as e:
                self.broadcastbot.logger.error(e, exc_info=True)
        # finally:
        #     raise StopPropagation

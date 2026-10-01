from __future__ import annotations

from signalblast.broadcastbot import BroadcastBot
from signalblast.commands import (
    AddAdmin,
    BanSubscriber,
    Broadcast,
    DisplayHelp,
    LastMsgUserUuid,
    LiftBanSubscriber,
    MessageFromAdmin,
    MessageToAdmin,
    RemoveAdmin,
    ShowVersion,
    Subscribe,
    Unsubscribe,
)
from signalblast.health_check import HealthCheck
from signalblast.settings import Settings
from signalblast.utils import configure_logging


def create_bot(settings: Settings) -> BroadcastBot:
    bot = BroadcastBot(settings)

    bot.signal_bot.register(Subscribe(bot=bot), groups=False)
    bot.signal_bot.register(Unsubscribe(bot=bot), groups=False)
    bot.signal_bot.register(Broadcast(bot=bot), groups=False)
    bot.signal_bot.register(DisplayHelp(bot=bot), groups=False)
    bot.signal_bot.register(AddAdmin(bot=bot), groups=False)
    bot.signal_bot.register(RemoveAdmin(bot=bot), groups=False)
    bot.signal_bot.register(BanSubscriber(bot=bot), groups=False)
    bot.signal_bot.register(LiftBanSubscriber(bot=bot), groups=False)
    bot.signal_bot.register(MessageToAdmin(bot=bot), groups=True)
    bot.signal_bot.register(MessageFromAdmin(bot=bot), groups=True)
    bot.signal_bot.register(LastMsgUserUuid(bot=bot), groups=True)
    bot.signal_bot.register(ShowVersion(bot=bot), groups=False)

    if settings.healthcheck_receiver is not None:
        bot.signal_bot.register(HealthCheck(settings.healthcheck_receiver, settings.healthcheck_port))

    bot.scheduler.add_job(bot.delete_old_timestamps, "interval", days=1)

    return bot


def main() -> None:
    settings = Settings()  # pyright: ignore[reportCallIssue] -- required fields come from the environment
    configure_logging(settings.log_level, settings.log_file)
    create_bot(settings).start()


if __name__ == "__main__":
    main()

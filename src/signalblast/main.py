from __future__ import annotations

import sys

from pydantic import ValidationError

from signalblast.broadcastbot import BroadcastBot
from signalblast.commands import register_handlers
from signalblast.health_check import HealthCheck
from signalblast.settings import Settings
from signalblast.utils import configure_logging


def create_bot(settings: Settings) -> BroadcastBot:
    bot = BroadcastBot(settings)

    # Only private chats, the bot has no group features
    register_handlers(bot)

    if settings.healthcheck_receiver is not None:
        bot.signal_bot.register(HealthCheck(settings.healthcheck_receiver, settings.healthcheck_port))

    bot.scheduler.add_job(bot.forget_old_messages, "interval", hours=1)

    return bot


def main() -> None:
    try:
        settings = Settings()  # pyright: ignore[reportCallIssue] -- required fields come from the environment
    except ValidationError as e:
        sys.exit(f"Invalid configuration, see .env.example for the SIGNALBLAST_* environment variables\n{e}")
    configure_logging(settings.log_level, settings.log_file)
    create_bot(settings).start()


if __name__ == "__main__":
    main()

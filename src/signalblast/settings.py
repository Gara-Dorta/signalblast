from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

FOUR_WEEKS = 60 * 60 * 24 * 7 * 4  # In seconds


class Settings(BaseSettings):
    """signalblast configuration, read from `SIGNALBLAST_*` environment variables or a `.env` file."""

    model_config = SettingsConfigDict(
        env_prefix="SIGNALBLAST_",
        env_file=".env",
        # docker compose passes unset .env values as empty strings, treat them as unset
        env_ignore_empty=True,
        # The .env file is shared with docker compose, which has its own variables
        extra="ignore",
    )

    phone_number: str = Field(description="The phone number of the bot")
    password: SecretStr | None = Field(
        default=None,
        description="The admin password. It is stored hashed, so it only needs to be set once or to change it",
    )
    signal_service: str = Field(default="localhost:8080", description="The address of signal-cli-rest-api")
    data_dir: Path = Field(
        default=Path.home() / ".local/share/signalblast",
        description="Where the database is stored",
    )
    expiration_time: int = Field(
        default=FOUR_WEEKS,
        ge=0,
        description="The disappearing messages timer for the subscribers chats in seconds, 0 to disable",
    )
    instructions_url: str | None = Field(default=None, description="URL with instructions, shown in the help message")
    healthcheck_receiver: str | None = Field(
        default=None,
        description="The contact or group that receives the health check messages, disables the health check if unset",
    )
    healthcheck_port: int = Field(default=15556, description="The port listening for health check requests")
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = Field(default="INFO")
    log_file: Path | None = Field(default=None, description="Log to this file instead of the console")

    @property
    def db_path(self) -> Path:
        return self.data_dir / "signalblast.db"

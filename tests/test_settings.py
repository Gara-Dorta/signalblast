from __future__ import annotations

from typing import TYPE_CHECKING

from signalblast.settings import FOUR_WEEKS, Settings

if TYPE_CHECKING:
    from pathlib import Path

    import pytest


def test_reads_prefixed_environment_variables(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SIGNALBLAST_PHONE_NUMBER", "+491234")
    monkeypatch.setenv("SIGNALBLAST_SIGNAL_SERVICE", "signal:9000")
    monkeypatch.setenv("SIGNALBLAST_EXPIRATION_TIME", "0")

    settings = Settings(_env_file=None)  # pyright: ignore[reportCallIssue]

    assert settings.phone_number == "+491234"
    assert settings.signal_service == "signal:9000"
    assert settings.expiration_time == 0


def test_empty_variables_are_treated_as_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    # docker compose passes unfilled .env values through as empty strings
    monkeypatch.setenv("SIGNALBLAST_PHONE_NUMBER", "+491234")
    monkeypatch.setenv("SIGNALBLAST_EXPIRATION_TIME", "")
    monkeypatch.setenv("SIGNALBLAST_HEALTHCHECK_RECEIVER", "")
    monkeypatch.setenv("SIGNALBLAST_PASSWORD", "")

    settings = Settings(_env_file=None)  # pyright: ignore[reportCallIssue]

    assert settings.expiration_time == FOUR_WEEKS
    assert settings.healthcheck_receiver is None
    assert settings.password is None


def test_env_file_shared_with_docker_compose(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text("DOCKER_TAG=latest\nSIGNALBLAST_PHONE_NUMBER=+491234\nSIGNALBLAST_PASSWORD=secret\n")
    monkeypatch.delenv("SIGNALBLAST_PHONE_NUMBER", raising=False)

    settings = Settings(_env_file=env_file)  # pyright: ignore[reportCallIssue]

    assert settings.phone_number == "+491234"
    assert settings.password is not None
    assert settings.password.get_secret_value() == "secret"
    assert "secret" not in repr(settings)

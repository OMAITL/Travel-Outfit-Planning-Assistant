import os

import pytest
from dotenv import load_dotenv
from pydantic import ValidationError

from src.config import Settings


def test_settings_loads_with_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_MODEL", raising=False)
    monkeypatch.delenv("OPENAI_API_BASE", raising=False)
    settings = Settings(_env_file=None)
    assert settings.openai_model == "deepseek-chat"
    assert settings.onebound_max_calls_per_run == 8


def test_dotenv_override_beats_system_env(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text("OPENAI_API_KEY=sk-from-project-env\n", encoding="utf-8")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-system-global-key")

    load_dotenv(env_file, override=True)
    assert os.environ["OPENAI_API_KEY"] == "sk-from-project-env"


def test_validate_llm_raises_when_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    settings = Settings(_env_file=None, openai_api_key=None)
    with pytest.raises(ValidationError):
        settings.validate_llm()


def test_validate_onebound_raises_when_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = Settings(_env_file=None, onebound_key=None, onebound_secret=None)
    with pytest.raises(ValidationError):
        settings.validate_onebound()

"""Local .env loading and secret precedence tests."""

from __future__ import annotations

import os

from travel_agent.infrastructure.solver import GaodeSettings
from travel_agent.runtime_config import load_runtime_environment


def test_runtime_environment_loads_explicit_dotenv_without_printing_values(
    tmp_path,
) -> None:
    dotenv = tmp_path / ".env"
    dotenv.write_text("TRAVEL_AGENT_TEST_DOTENV=loaded\n", encoding="utf-8")
    os.environ.pop("TRAVEL_AGENT_TEST_DOTENV", None)

    try:
        loaded = load_runtime_environment(dotenv)

        assert loaded == dotenv
        assert os.environ["TRAVEL_AGENT_TEST_DOTENV"] == "loaded"
    finally:
        os.environ.pop("TRAVEL_AGENT_TEST_DOTENV", None)


def test_process_environment_overrides_dotenv(monkeypatch, tmp_path) -> None:
    dotenv = tmp_path / ".env"
    dotenv.write_text(
        "TRAVEL_AGENT_GAODE_API_KEY=dotenv-secret\n"
        "TRAVEL_AGENT_GAODE_CITY_CODE=000000\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("TRAVEL_AGENT_GAODE_API_KEY", "deployment-secret")
    monkeypatch.setenv("TRAVEL_AGENT_GAODE_CITY_CODE", "330100")

    settings = GaodeSettings.from_env(dotenv_path=dotenv)

    assert settings.api_key == "deployment-secret"
    assert settings.city_code == "330100"
    assert "deployment-secret" not in repr(settings)


def test_missing_explicit_dotenv_is_non_blocking(tmp_path) -> None:
    assert load_runtime_environment(tmp_path / "missing.env") is None

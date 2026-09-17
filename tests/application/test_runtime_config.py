"""Local .env loading and secret precedence tests."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from travel_agent.infrastructure.solver import GaodeSettings
from travel_agent.runtime_config import load_runtime_environment


def test_runtime_environment_loads_explicit_dotenv_without_printing_values(
    tmp_path: Path,
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


def test_process_environment_overrides_dotenv(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    dotenv = tmp_path / ".env"
    dotenv.write_text(
        "TRAVEL_AGENT_GAODE_API_KEY=dotenv-secret\nTRAVEL_AGENT_GAODE_CITY_CODE=000000\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("TRAVEL_AGENT_GAODE_API_KEY", "deployment-secret")
    monkeypatch.setenv("TRAVEL_AGENT_GAODE_CITY_CODE", "330100")

    settings = GaodeSettings.from_env(dotenv_path=dotenv)

    assert settings.api_key == "deployment-secret"
    assert settings.city_code == "330100"
    assert "deployment-secret" not in repr(settings)


def test_missing_explicit_dotenv_is_non_blocking(tmp_path: Path) -> None:
    assert load_runtime_environment(tmp_path / "missing.env") is None


def test_mounted_config_overrides_environment_and_skips_dotenv(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """G7-R0.3: one authoritative production file, including literal secrets."""
    config = tmp_path / "mounted.env"
    config.write_text(
        'TRAVEL_AGENT_GAODE_API_KEY = "literal-$VALUE-#-secret"\n'
        'TRAVEL_AGENT_GAODE_CITY_CODE = "330100"\n', encoding="utf-8"
    )
    dotenv = tmp_path / ".env"
    dotenv.write_text("TRAVEL_AGENT_GAODE_CITY_CODE=000000\n", encoding="utf-8")
    monkeypatch.setenv("TRAVEL_AGENT_CONFIG_FILE", str(config))
    monkeypatch.setenv("TRAVEL_AGENT_GAODE_API_KEY", "stale")
    monkeypatch.setenv("TRAVEL_AGENT_GAODE_CITY_CODE", "stale")
    settings = GaodeSettings.from_env(dotenv_path=dotenv)
    assert settings.api_key == "literal-$VALUE-#-secret"
    assert settings.city_code == "330100"


@pytest.mark.parametrize("contents", [None, "secret-invalid", "[wrong]", 'PATH="x"',
                                     'TRAVEL_AGENT_X="secret'])
def test_mounted_config_fails_closed_without_secret_output(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, contents: str | None
) -> None:
    config = tmp_path / "mounted.env"
    if contents is not None:
        config.write_text(contents, encoding="utf-8")
    monkeypatch.setenv("TRAVEL_AGENT_CONFIG_FILE", str(config))
    with pytest.raises(ValueError) as error:
        load_runtime_environment()
    assert "secret" not in str(error.value)


def test_mounted_config_validation_does_not_partially_apply(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    config = tmp_path / "mounted.env"
    config.write_text('TRAVEL_AGENT_TEST_VALUE="new"\nPATH="bad"', encoding="utf-8")
    monkeypatch.setenv("TRAVEL_AGENT_CONFIG_FILE", str(config))
    monkeypatch.setenv("TRAVEL_AGENT_TEST_VALUE", "old")
    with pytest.raises(ValueError):
        load_runtime_environment()
    assert os.environ["TRAVEL_AGENT_TEST_VALUE"] == "old"

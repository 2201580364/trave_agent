"""Explicit local ``.env`` loading with deployment environment precedence."""

from __future__ import annotations

import os
import re
from os import PathLike
from pathlib import Path

from dotenv import dotenv_values, find_dotenv, load_dotenv
from dotenv.parser import parse_stream


def _load_mounted_config(path: Path) -> Path:
    """G7-R0.3: mounted configuration is authoritative; never echo secrets."""
    try:
        with path.open(encoding="utf-8") as stream:
            bindings = list(parse_stream(stream))
        if any(binding.error for binding in bindings):
            raise ValueError
        for binding in bindings:
            if binding.key is not None and (
                not re.fullmatch(r"TRAVEL_AGENT_[A-Z0-9_]+", binding.key)
                or binding.key == "TRAVEL_AGENT_CONFIG_FILE"
                or binding.value is None
            ):
                raise ValueError
        parsed = dotenv_values(path, encoding="utf-8")
        values = {}
        for key, value in parsed.items():
            if value is None or "\x00" in value:
                raise ValueError
            values[key] = value
    except (OSError, ValueError):
        raise ValueError("Mounted .env configuration is missing or invalid") from None
    # Validate the entire document before changing any process state.
    os.environ.update(values)
    return path


def load_runtime_environment(
    dotenv_path: str | PathLike[str] | None = None,
) -> Path | None:
    """Load a local ``.env`` without overriding process environment values.

    When no path is supplied, lookup starts at the current working directory.
    This keeps repository-local development convenient while allowing Docker,
    CI/CD and service-manager secrets to take precedence in deployed runtimes.
    """

    mounted_path = os.environ.get("TRAVEL_AGENT_CONFIG_FILE")
    if mounted_path:
        return _load_mounted_config(Path(mounted_path))

    resolved: Path | None
    if dotenv_path is None:
        discovered = find_dotenv(filename=".env", usecwd=True)
        resolved = Path(discovered) if discovered else None
    else:
        candidate = Path(dotenv_path)
        resolved = candidate if candidate.is_file() else None

    if resolved is None:
        return None
    load_dotenv(dotenv_path=resolved, override=False, encoding="utf-8")
    return resolved

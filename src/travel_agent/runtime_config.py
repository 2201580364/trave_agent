"""Explicit local ``.env`` loading with deployment environment precedence."""

from __future__ import annotations

from os import PathLike
from pathlib import Path

from dotenv import find_dotenv, load_dotenv


def load_runtime_environment(
    dotenv_path: str | PathLike[str] | None = None,
) -> Path | None:
    """Load a local ``.env`` without overriding process environment values.

    When no path is supplied, lookup starts at the current working directory.
    This keeps repository-local development convenient while allowing Docker,
    CI/CD and service-manager secrets to take precedence in deployed runtimes.
    """

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

"""Run the production-style HTTP composition with a published JSON snapshot."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--dotenv", type=Path, default=ROOT / ".env")
    args = parser.parse_args()

    from travel_agent.interfaces.http import (
        ProductionHttpSettings,
        build_production_http_app,
    )
    from travel_agent.observability import configure_file_logging

    settings = ProductionHttpSettings.from_env(dotenv_path=args.dotenv)
    app = build_production_http_app(settings)
    configure_file_logging(ROOT / "logs", component="api", enable_console=False)

    import uvicorn

    uvicorn.run(app, host=args.host, port=args.port, access_log=False)


if __name__ == "__main__":
    main()

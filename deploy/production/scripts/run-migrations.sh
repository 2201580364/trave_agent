#!/usr/bin/env bash
set -euo pipefail
if [[ "${EUID}" -ne 0 ]]; then
  echo "run-migrations.sh must run as root" >&2
  exit 1
fi
if [[ "${1:-}" != "--apply" ]]; then
  echo '{"status":"ok","dry_run":true,"actions":["Compose migrate: alembic upgrade head"]}'
  exit 0
fi
docker compose -f /opt/travel-agent/infra/docker-compose.yml --profile tools run --no-deps migrate
echo '{"status":"ok","migration":"complete"}'

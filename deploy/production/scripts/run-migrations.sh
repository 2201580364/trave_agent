#!/usr/bin/env bash
set -euo pipefail

if [[ "${EUID}" -ne 0 ]]; then
  echo "run-migrations.sh must run as root" >&2
  exit 1
fi

set -a
source /etc/travel-agent/infra.env
set +a

APP_ROOT=/opt/travel-agent/app
VENV_ROOT=/opt/travel-agent/venv

if [[ ! -x "${VENV_ROOT}/bin/alembic" || ! -f "${APP_ROOT}/alembic.ini" ]]; then
  echo "Travel Agent application or Alembic environment is not installed" >&2
  exit 1
fi

export TRAVEL_AGENT_DATABASE_URL="mysql+pymysql://${MYSQL_MIGRATION_USER}:${MYSQL_MIGRATION_PASSWORD}@127.0.0.1:${MYSQL_BIND_PORT}/${MYSQL_DATABASE}?charset=utf8mb4"

cd "${APP_ROOT}"
"${VENV_ROOT}/bin/alembic" -c alembic.ini upgrade head
"${VENV_ROOT}/bin/alembic" -c alembic.ini current

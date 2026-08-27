#!/usr/bin/env bash
set -euo pipefail

if [[ "${EUID}" -ne 0 ]]; then
  echo "validate-persistence.sh must run as root" >&2
  exit 1
fi

set -a
source /etc/travel-agent/infra.env
set +a

export TRAVEL_AGENT_DATABASE_URL="mysql+pymysql://${MYSQL_APP_USER}:${MYSQL_APP_PASSWORD}@127.0.0.1:${MYSQL_BIND_PORT}/${MYSQL_DATABASE}?charset=utf8mb4"

/opt/travel-agent/venv/bin/python \
  /opt/travel-agent/infra/validation/validate_mysql_persistence.py

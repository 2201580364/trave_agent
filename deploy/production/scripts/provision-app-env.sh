#!/usr/bin/env bash
set -euo pipefail

if [[ "${EUID}" -ne 0 ]]; then
  echo "provision-app-env.sh must run as root" >&2
  exit 1
fi

set -a
source /etc/travel-agent/infra.env
set +a

APP_ENV=/etc/travel-agent/app.env
if [[ -e "${APP_ENV}" ]]; then
  echo "Refusing to overwrite existing ${APP_ENV}" >&2
  exit 1
fi

umask 077
cat >"${APP_ENV}" <<EOF
TRAVEL_AGENT_DATABASE_URL=mysql+pymysql://${MYSQL_APP_USER}:${MYSQL_APP_PASSWORD}@127.0.0.1:${MYSQL_BIND_PORT}/${MYSQL_DATABASE}?charset=utf8mb4
TRAVEL_AGENT_DATABASE_ECHO=false
TRAVEL_AGENT_DB_POOL_SIZE=5
TRAVEL_AGENT_DB_MAX_OVERFLOW=5
TRAVEL_AGENT_DB_POOL_RECYCLE_SECONDS=1800
TRAVEL_AGENT_DB_POOL_TIMEOUT_SECONDS=30
TRAVEL_AGENT_PROVIDER_REDIS_URL=redis://${REDIS_APP_USER}:${REDIS_PASSWORD}@127.0.0.1:${REDIS_BIND_PORT}/0
TRAVEL_AGENT_PROVIDER_REDIS_PREFIX=${REDIS_KEY_PREFIX}
EOF

chmod 0600 "${APP_ENV}"
echo "Application database and Redis environment created without printing URLs."

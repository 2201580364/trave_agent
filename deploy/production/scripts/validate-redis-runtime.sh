#!/usr/bin/env bash
set -euo pipefail

if [[ "${EUID}" -ne 0 ]]; then
  echo "validate-redis-runtime.sh must run as root" >&2
  exit 1
fi

set -a
source /etc/travel-agent/infra.env
set +a

export TRAVEL_AGENT_PROVIDER_REDIS_URL="redis://${REDIS_APP_USER}:${REDIS_PASSWORD}@127.0.0.1:${REDIS_BIND_PORT}/0"

/opt/travel-agent/venv/bin/python \
  /opt/travel-agent/infra/validation/validate_redis_runtime.py

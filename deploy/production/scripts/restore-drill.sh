#!/usr/bin/env bash
set -euo pipefail

if [[ "${EUID}" -ne 0 ]]; then
  echo "restore-drill.sh must run as root" >&2
  exit 1
fi

BACKUP_ROOT=/srv/travel-agent/backups
CHECKSUM_FILE=${1:-}

if [[ -z "${CHECKSUM_FILE}" ]]; then
  CHECKSUM_FILE=$(find "${BACKUP_ROOT}" -maxdepth 1 -type f \
    -name 'checksums-*.sha256' -printf '%T@ %p\n' \
    | sort -nr | head -n 1 | cut -d' ' -f2-)
fi

if [[ -z "${CHECKSUM_FILE}" || ! -f "${CHECKSUM_FILE}" ]]; then
  echo "No checksum manifest was found" >&2
  exit 1
fi

CHECKSUM_FILE=$(readlink -f -- "${CHECKSUM_FILE}")
case "${CHECKSUM_FILE}" in
  "${BACKUP_ROOT}"/checksums-*.sha256) ;;
  *)
    echo "Checksum manifest must be under ${BACKUP_ROOT}" >&2
    exit 1
    ;;
esac

MYSQL_BACKUP=$(awk '$2 ~ /\/mysql\/travel-agent-.*\.sql\.gz$/ { print $2 }' \
  "${CHECKSUM_FILE}")
REDIS_BACKUP=$(awk '$2 ~ /\/redis\/travel-agent-.*\.rdb$/ { print $2 }' \
  "${CHECKSUM_FILE}")

if [[ ! -f "${MYSQL_BACKUP}" || ! -f "${REDIS_BACKUP}" ]]; then
  echo "Checksum manifest does not reference both expected backup files" >&2
  exit 1
fi

sha256sum --check "${CHECKSUM_FILE}"

RUN_ID=$(date -u +%Y%m%dT%H%M%SZ)-$$
MYSQL_CONTAINER=travel-agent-restore-mysql-${RUN_ID}
REDIS_CONTAINER=travel-agent-restore-redis-${RUN_ID}
MYSQL_VOLUME=travel-agent-restore-mysql-${RUN_ID}
REDIS_VOLUME=travel-agent-restore-redis-${RUN_ID}
MYSQL_RESTORE_PASSWORD=$(openssl rand -hex 24)

cleanup() {
  docker rm -f "${MYSQL_CONTAINER}" "${REDIS_CONTAINER}" \
    >/dev/null 2>&1 || true
  docker volume rm "${MYSQL_VOLUME}" "${REDIS_VOLUME}" \
    >/dev/null 2>&1 || true
}

trap cleanup EXIT

docker volume create "${MYSQL_VOLUME}" >/dev/null
docker volume create "${REDIS_VOLUME}" >/dev/null

docker run -d --name "${MYSQL_CONTAINER}" \
  --network none \
  -e MYSQL_ROOT_PASSWORD="${MYSQL_RESTORE_PASSWORD}" \
  -e MYSQL_DATABASE=travel_agent_restore \
  -v "${MYSQL_VOLUME}:/var/lib/mysql" \
  mysql:8.0 \
  --character-set-server=utf8mb4 \
  --collation-server=utf8mb4_0900_ai_ci \
  --default-time-zone=+00:00 >/dev/null

MYSQL_READY=false
for _attempt in $(seq 1 90); do
  if docker exec \
    -e MYSQL_PWD="${MYSQL_RESTORE_PASSWORD}" \
    "${MYSQL_CONTAINER}" \
    mysql --protocol=socket -uroot --batch --skip-column-names \
      -e "SELECT 1;" >/dev/null 2>&1; then
    MYSQL_READY=true
    break
  fi
  sleep 1
done

if [[ "${MYSQL_READY}" != true ]]; then
  echo "Isolated MySQL restore container did not become ready" >&2
  exit 1
fi

gzip -dc -- "${MYSQL_BACKUP}" \
  | docker exec -i \
      -e MYSQL_PWD="${MYSQL_RESTORE_PASSWORD}" \
      "${MYSQL_CONTAINER}" \
      mysql --protocol=socket -uroot travel_agent_restore

MYSQL_TABLE_COUNT=$(docker exec \
  -e MYSQL_PWD="${MYSQL_RESTORE_PASSWORD}" \
  "${MYSQL_CONTAINER}" \
  mysql --protocol=socket -uroot -Nse \
    "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='travel_agent_restore';")
MYSQL_ALEMBIC_REVISION=$(docker exec \
  -e MYSQL_PWD="${MYSQL_RESTORE_PASSWORD}" \
  "${MYSQL_CONTAINER}" \
  mysql --protocol=socket -uroot -Nse \
    "SELECT version_num FROM travel_agent_restore.alembic_version LIMIT 1;")

if [[ "${MYSQL_TABLE_COUNT}" -le 0 || -z "${MYSQL_ALEMBIC_REVISION}" ]]; then
  echo "Isolated MySQL restore is missing tables or Alembic revision" >&2
  exit 1
fi

docker run --rm --user 0 \
  -v "${REDIS_BACKUP}:/input/dump.rdb:ro" \
  -v "${REDIS_VOLUME}:/data" \
  redis:7.4-alpine \
  sh -c 'cp /input/dump.rdb /data/dump.rdb && chown redis:redis /data/dump.rdb'

docker run -d --name "${REDIS_CONTAINER}" \
  --network none \
  -v "${REDIS_VOLUME}:/data" \
  redis:7.4-alpine \
  redis-server --appendonly no --save '' --protected-mode no >/dev/null

REDIS_READY=false
for _attempt in $(seq 1 30); do
  if docker exec "${REDIS_CONTAINER}" redis-cli ping \
    | grep -q '^PONG$'; then
    REDIS_READY=true
    break
  fi
  sleep 1
done

if [[ "${REDIS_READY}" != true ]]; then
  echo "Isolated Redis restore container did not become ready" >&2
  exit 1
fi

REDIS_KEY_COUNT=$(docker exec "${REDIS_CONTAINER}" redis-cli DBSIZE)

echo "Isolated restore drill passed."
echo "MySQL tables: ${MYSQL_TABLE_COUNT}; Alembic revision: ${MYSQL_ALEMBIC_REVISION}."
echo "Redis keys loaded: ${REDIS_KEY_COUNT}."

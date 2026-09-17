#!/usr/bin/env bash
set -euo pipefail

if [[ "${EUID}" -ne 0 ]]; then
  echo "backup.sh must run as root" >&2
  exit 1
fi

# G7-R0.3: credentials are read inside containers from read-only mounts.
if [[ "${1:-}" != "--apply" ]]; then
  echo '{"status":"ok","dry_run":true,"actions":["MySQL logical backup","Redis BGSAVE","SHA-256 manifest"],"deletes":false}'
  exit 0
fi
redis_admin() {
  docker exec travel-agent-redis sh -c 'export REDISCLI_AUTH="$(cat /etc/redis/admin-password)"; exec redis-cli --user "$(cat /etc/redis/admin-user)" "$@"' sh "$@"
}

BACKUP_ROOT=/srv/travel-agent/backups
STAMP=$(date -u +%Y%m%dT%H%M%SZ)
MYSQL_OUTPUT=${BACKUP_ROOT}/mysql/travel-agent-${STAMP}.sql.gz
REDIS_OUTPUT=${BACKUP_ROOT}/redis/travel-agent-${STAMP}.rdb
MYSQL_PARTIAL=${MYSQL_OUTPUT}.partial
REDIS_PARTIAL=${REDIS_OUTPUT}.partial
CHECKSUM_OUTPUT=${BACKUP_ROOT}/checksums-${STAMP}.sha256
# Retention cleanup is manual; this command never deletes backup files.

umask 077
install -d -m 0750 "${BACKUP_ROOT}/mysql" "${BACKUP_ROOT}/redis"

docker exec travel-agent-mysql \
  mysqldump --defaults-extra-file=/etc/travel-agent/mysql/clients/backup.cnf \
    --protocol=socket --single-transaction --events --triggers --hex-blob --no-tablespaces \
    "$(cat /etc/travel-agent/mysql/clients/database)" \
  | gzip -9 >"${MYSQL_PARTIAL}"
mv -- "${MYSQL_PARTIAL}" "${MYSQL_OUTPUT}"

redis_admin BGSAVE >/dev/null

REDIS_SAVE_COMPLETED=false
for _attempt in $(seq 1 60); do
  REDIS_PERSISTENCE=$(redis_admin INFO persistence | tr -d '\r')
  if grep -q '^rdb_bgsave_in_progress:0$' <<<"${REDIS_PERSISTENCE}" \
    && grep -q '^rdb_last_bgsave_status:ok$' <<<"${REDIS_PERSISTENCE}"; then
    REDIS_SAVE_COMPLETED=true
    break
  fi
  sleep 1
done

if [[ "${REDIS_SAVE_COMPLETED}" != true ]]; then
  echo "Redis BGSAVE did not complete successfully within 60 seconds" >&2
  exit 1
fi

docker cp travel-agent-redis:/data/dump.rdb "${REDIS_PARTIAL}" >/dev/null
mv -- "${REDIS_PARTIAL}" "${REDIS_OUTPUT}"
chmod 0600 "${MYSQL_OUTPUT}" "${REDIS_OUTPUT}"
sha256sum "${MYSQL_OUTPUT}" "${REDIS_OUTPUT}" \
  >"${CHECKSUM_OUTPUT}"
chmod 0600 "${CHECKSUM_OUTPUT}"

echo "{\"status\":\"ok\",\"timestamp\":\"${STAMP}\",\"checksum_manifest\":\"${CHECKSUM_OUTPUT}\"}"

#!/usr/bin/env bash
set -euo pipefail

if [[ "${EUID}" -ne 0 ]]; then
  echo "backup.sh must run as root" >&2
  exit 1
fi

set -a
source /etc/travel-agent/infra.env
set +a

BACKUP_ROOT=/srv/travel-agent/backups
STAMP=$(date -u +%Y%m%dT%H%M%SZ)
MYSQL_OUTPUT=${BACKUP_ROOT}/mysql/travel-agent-${STAMP}.sql.gz
REDIS_OUTPUT=${BACKUP_ROOT}/redis/travel-agent-${STAMP}.rdb
MYSQL_PARTIAL=${MYSQL_OUTPUT}.partial
REDIS_PARTIAL=${REDIS_OUTPUT}.partial
CHECKSUM_OUTPUT=${BACKUP_ROOT}/checksums-${STAMP}.sha256
RETENTION_DAYS=${BACKUP_RETENTION_DAYS:-14}

cleanup_partial_files() {
  rm -f -- "${MYSQL_PARTIAL}" "${REDIS_PARTIAL}"
}

trap cleanup_partial_files EXIT

umask 077
install -d -m 0750 "${BACKUP_ROOT}/mysql" "${BACKUP_ROOT}/redis"

docker exec \
  -e MYSQL_PWD="${MYSQL_BACKUP_PASSWORD}" \
  travel-agent-mysql \
  mysqldump --protocol=socket -u"${MYSQL_BACKUP_USER}" \
    --single-transaction --events --triggers --hex-blob --no-tablespaces \
    "${MYSQL_DATABASE}" \
  | gzip -9 >"${MYSQL_PARTIAL}"
mv -- "${MYSQL_PARTIAL}" "${MYSQL_OUTPUT}"

REDIS_LASTSAVE_BEFORE=$(docker exec travel-agent-redis \
  redis-cli --user "${REDIS_ADMIN_USER}" \
    --pass "${REDIS_ADMIN_PASSWORD}" --no-auth-warning LASTSAVE)

docker exec travel-agent-redis \
  redis-cli --user "${REDIS_ADMIN_USER}" \
    --pass "${REDIS_ADMIN_PASSWORD}" --no-auth-warning BGSAVE >/dev/null

REDIS_SAVE_COMPLETED=false
for _attempt in $(seq 1 60); do
  REDIS_PERSISTENCE=$(docker exec travel-agent-redis \
    redis-cli --user "${REDIS_ADMIN_USER}" \
      --pass "${REDIS_ADMIN_PASSWORD}" --no-auth-warning \
      INFO persistence | tr -d '\r')
  REDIS_LASTSAVE_AFTER=$(docker exec travel-agent-redis \
    redis-cli --user "${REDIS_ADMIN_USER}" \
      --pass "${REDIS_ADMIN_PASSWORD}" --no-auth-warning LASTSAVE)

  if grep -q '^rdb_bgsave_in_progress:0$' <<<"${REDIS_PERSISTENCE}" \
    && grep -q '^rdb_last_bgsave_status:ok$' <<<"${REDIS_PERSISTENCE}" \
    && (( REDIS_LASTSAVE_AFTER > REDIS_LASTSAVE_BEFORE )); then
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

find "${BACKUP_ROOT}/mysql" -type f -name 'travel-agent-*.sql.gz' -mtime +"${RETENTION_DAYS}" -delete
find "${BACKUP_ROOT}/redis" -type f -name 'travel-agent-*.rdb' -mtime +"${RETENTION_DAYS}" -delete
find "${BACKUP_ROOT}" -maxdepth 1 -type f -name 'checksums-*.sha256' -mtime +"${RETENTION_DAYS}" -delete

trap - EXIT
echo "Backup completed at ${STAMP}."

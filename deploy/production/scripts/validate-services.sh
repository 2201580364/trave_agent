#!/usr/bin/env bash
set -euo pipefail

if [[ "${EUID}" -ne 0 ]]; then
  echo "validate-services.sh must run as root" >&2
  exit 1
fi

set -a
source /etc/travel-agent/infra.env
set +a

mysql_exec() {
  local user=$1
  local password=$2
  shift 2
  docker exec \
    -e MYSQL_PWD="${password}" \
    travel-agent-mysql \
    mysql --protocol=socket --batch --skip-column-names \
      -u"${user}" "$@"
}

MYSQL_FACTS=$(mysql_exec root "${MYSQL_ROOT_PASSWORD}" -e \
  "SELECT VERSION(), @@default_storage_engine, @@character_set_server, @@collation_server, @@global.time_zone;")
IFS=$'\t' read -r MYSQL_VERSION MYSQL_ENGINE MYSQL_CHARSET MYSQL_COLLATION MYSQL_TIMEZONE \
  <<<"${MYSQL_FACTS}"

[[ "${MYSQL_ENGINE}" == "InnoDB" ]]
[[ "${MYSQL_CHARSET}" == "utf8mb4" ]]
[[ "${MYSQL_COLLATION}" == "utf8mb4_0900_ai_ci" ]]
[[ "${MYSQL_TIMEZONE}" == "+00:00" ]]

mysql_exec "${MYSQL_APP_USER}" "${MYSQL_APP_PASSWORD}" \
  "${MYSQL_DATABASE}" -e "SELECT 1;" >/dev/null

if mysql_exec "${MYSQL_APP_USER}" "${MYSQL_APP_PASSWORD}" \
  "${MYSQL_DATABASE}" -e \
  "CREATE TABLE validation_app_must_not_create (id INT PRIMARY KEY);" \
  >/dev/null 2>&1; then
  mysql_exec root "${MYSQL_ROOT_PASSWORD}" "${MYSQL_DATABASE}" -e \
    "DROP TABLE IF EXISTS validation_app_must_not_create;" >/dev/null
  echo "MySQL application account unexpectedly obtained DDL permission" >&2
  exit 1
fi

mysql_exec "${MYSQL_MIGRATION_USER}" "${MYSQL_MIGRATION_PASSWORD}" \
  "${MYSQL_DATABASE}" -e \
  "CREATE TABLE validation_migration_ddl (id INT PRIMARY KEY); DROP TABLE validation_migration_ddl;" \
  >/dev/null

mysql_exec "${MYSQL_BACKUP_USER}" "${MYSQL_BACKUP_PASSWORD}" \
  "${MYSQL_DATABASE}" -e "SELECT COUNT(*) FROM alembic_version;" >/dev/null
if mysql_exec "${MYSQL_BACKUP_USER}" "${MYSQL_BACKUP_PASSWORD}" \
  "${MYSQL_DATABASE}" -e \
  "INSERT INTO alembic_version (version_num) VALUES ('backup_must_not_write');" \
  >/dev/null 2>&1; then
  mysql_exec root "${MYSQL_ROOT_PASSWORD}" "${MYSQL_DATABASE}" -e \
    "DELETE FROM alembic_version WHERE version_num='backup_must_not_write';" >/dev/null
  echo "MySQL backup account unexpectedly obtained write permission" >&2
  exit 1
fi

REDIS_TEST_KEY="${REDIS_KEY_PREFIX}:validation:acl"
docker exec travel-agent-redis \
  redis-cli --user "${REDIS_APP_USER}" \
    --pass "${REDIS_PASSWORD}" --no-auth-warning \
    SET "${REDIS_TEST_KEY}" ok EX 60 >/dev/null
REDIS_VALUE=$(docker exec travel-agent-redis \
  redis-cli --user "${REDIS_APP_USER}" \
    --pass "${REDIS_PASSWORD}" --no-auth-warning \
    GET "${REDIS_TEST_KEY}")
[[ "${REDIS_VALUE}" == "ok" ]]
docker exec travel-agent-redis \
  redis-cli --user "${REDIS_APP_USER}" \
    --pass "${REDIS_PASSWORD}" --no-auth-warning \
    DEL "${REDIS_TEST_KEY}" >/dev/null

REDIS_PREFIX_DENIAL=$(docker exec travel-agent-redis \
  redis-cli --user "${REDIS_APP_USER}" \
    --pass "${REDIS_PASSWORD}" --no-auth-warning \
    SET outside-prefix:validation denied 2>&1 || true)
grep -q 'NOPERM' <<<"${REDIS_PREFIX_DENIAL}"

REDIS_COMMAND_DENIAL=$(docker exec travel-agent-redis \
  redis-cli --user "${REDIS_APP_USER}" \
    --pass "${REDIS_PASSWORD}" --no-auth-warning \
    CONFIG GET maxmemory 2>&1 || true)
grep -q 'NOPERM' <<<"${REDIS_COMMAND_DENIAL}"

MYSQL_LOCAL_ADDRESS=$(ss -H -lnt "sport = :${MYSQL_BIND_PORT}" | awk '{print $4}')
REDIS_LOCAL_ADDRESS=$(ss -H -lnt "sport = :${REDIS_BIND_PORT}" | awk '{print $4}')
if [[ "${MYSQL_LOCAL_ADDRESS}" != "127.0.0.1:${MYSQL_BIND_PORT}" \
  || "${REDIS_LOCAL_ADDRESS}" != "127.0.0.1:${REDIS_BIND_PORT}" ]]; then
  echo "Travel Agent database listener is exposed beyond loopback" >&2
  exit 1
fi

echo "Service validation passed."
echo "MySQL ${MYSQL_VERSION}: ${MYSQL_ENGINE}, ${MYSQL_CHARSET}, ${MYSQL_COLLATION}, UTC."
echo "MySQL application DDL denied; migration DDL allowed."
echo "MySQL backup account is read-only and scoped to backup metadata."
echo "Redis prefix and command ACL restrictions passed."
echo "MySQL/Redis host ports are loopback-only (${MYSQL_BIND_PORT}/${REDIS_BIND_PORT})."

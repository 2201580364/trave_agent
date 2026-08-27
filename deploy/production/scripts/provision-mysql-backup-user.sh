#!/usr/bin/env bash
set -euo pipefail

if [[ "${EUID}" -ne 0 ]]; then
  echo "provision-mysql-backup-user.sh must run as root" >&2
  exit 1
fi

ENV_FILE=/etc/travel-agent/infra.env
set -a
source "${ENV_FILE}"
set +a

if [[ -z "${MYSQL_BACKUP_USER:-}" || -z "${MYSQL_BACKUP_PASSWORD:-}" ]]; then
  MYSQL_BACKUP_USER=travel_agent_backup
  MYSQL_BACKUP_PASSWORD=$(openssl rand -hex 24)
  umask 077
  {
    printf 'MYSQL_BACKUP_USER=%s\n' "${MYSQL_BACKUP_USER}"
    printf 'MYSQL_BACKUP_PASSWORD=%s\n' "${MYSQL_BACKUP_PASSWORD}"
  } >>"${ENV_FILE}"
fi

docker exec -i \
  -e MYSQL_PWD="${MYSQL_ROOT_PASSWORD}" \
  travel-agent-mysql \
  mysql --protocol=socket -uroot <<SQL
CREATE USER IF NOT EXISTS '${MYSQL_BACKUP_USER}'@'%'
  IDENTIFIED BY '${MYSQL_BACKUP_PASSWORD}';
ALTER USER '${MYSQL_BACKUP_USER}'@'%'
  IDENTIFIED BY '${MYSQL_BACKUP_PASSWORD}';
GRANT SELECT, SHOW VIEW, TRIGGER, EVENT, LOCK TABLES
  ON ${MYSQL_DATABASE}.* TO '${MYSQL_BACKUP_USER}'@'%';
FLUSH PRIVILEGES;
SQL

chmod 0600 "${ENV_FILE}"
echo "MySQL backup user provisioned without printing credentials."

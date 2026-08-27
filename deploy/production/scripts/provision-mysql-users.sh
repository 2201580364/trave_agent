#!/usr/bin/env bash
set -euo pipefail

if [[ "${EUID}" -ne 0 ]]; then
  echo "provision-mysql-users.sh must run as root" >&2
  exit 1
fi

set -a
source /etc/travel-agent/infra.env
set +a

docker exec -i \
  -e MYSQL_PWD="${MYSQL_ROOT_PASSWORD}" \
  travel-agent-mysql \
  mysql --protocol=socket -uroot <<SQL
CREATE USER IF NOT EXISTS '${MYSQL_APP_USER}'@'%' IDENTIFIED BY '${MYSQL_APP_PASSWORD}';
ALTER USER '${MYSQL_APP_USER}'@'%' IDENTIFIED BY '${MYSQL_APP_PASSWORD}';
GRANT SELECT, INSERT, UPDATE, DELETE
  ON ${MYSQL_DATABASE}.* TO '${MYSQL_APP_USER}'@'%';

CREATE USER IF NOT EXISTS '${MYSQL_MIGRATION_USER}'@'%'
  IDENTIFIED BY '${MYSQL_MIGRATION_PASSWORD}';
ALTER USER '${MYSQL_MIGRATION_USER}'@'%'
  IDENTIFIED BY '${MYSQL_MIGRATION_PASSWORD}';
GRANT SELECT, INSERT, UPDATE, DELETE, CREATE, ALTER, INDEX, DROP,
  REFERENCES, CREATE VIEW, SHOW VIEW, TRIGGER
  ON ${MYSQL_DATABASE}.* TO '${MYSQL_MIGRATION_USER}'@'%';

FLUSH PRIVILEGES;
SQL

echo "MySQL application and migration users provisioned."


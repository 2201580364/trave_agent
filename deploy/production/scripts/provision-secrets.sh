#!/usr/bin/env bash
set -euo pipefail

if [[ "${EUID}" -ne 0 ]]; then
  echo "provision-secrets.sh must run as root" >&2
  exit 1
fi

ENV_DIR=/etc/travel-agent
ENV_FILE=${ENV_DIR}/infra.env
REDIS_DIR=${ENV_DIR}/redis
REDIS_ACL=${REDIS_DIR}/users.acl

install -d -m 0750 -o root -g root "${ENV_DIR}" "${REDIS_DIR}"
install -d -m 0750 -o root -g root \
  /srv/travel-agent/data/mysql \
  /srv/travel-agent/data/redis \
  /srv/travel-agent/backups/mysql \
  /srv/travel-agent/backups/redis

if [[ -e "${ENV_FILE}" ]]; then
  echo "Refusing to overwrite existing ${ENV_FILE}" >&2
  exit 1
fi

MYSQL_ROOT_PASSWORD=$(openssl rand -hex 24)
MYSQL_APP_PASSWORD=$(openssl rand -hex 24)
MYSQL_MIGRATION_PASSWORD=$(openssl rand -hex 24)
MYSQL_BACKUP_PASSWORD=$(openssl rand -hex 24)
REDIS_PASSWORD=$(openssl rand -hex 24)
REDIS_ADMIN_PASSWORD=$(openssl rand -hex 24)

umask 077
cat >"${ENV_FILE}" <<EOF
MYSQL_ROOT_PASSWORD=${MYSQL_ROOT_PASSWORD}
MYSQL_DATABASE=travel_agent
MYSQL_APP_USER=travel_agent_app
MYSQL_APP_PASSWORD=${MYSQL_APP_PASSWORD}
MYSQL_MIGRATION_USER=travel_agent_migration
MYSQL_MIGRATION_PASSWORD=${MYSQL_MIGRATION_PASSWORD}
MYSQL_BACKUP_USER=travel_agent_backup
MYSQL_BACKUP_PASSWORD=${MYSQL_BACKUP_PASSWORD}
MYSQL_BIND_PORT=13306
REDIS_APP_USER=travel_agent
REDIS_PASSWORD=${REDIS_PASSWORD}
REDIS_ADMIN_USER=travel_agent_admin
REDIS_ADMIN_PASSWORD=${REDIS_ADMIN_PASSWORD}
REDIS_BIND_PORT=16379
REDIS_KEY_PREFIX=travel-agent
EOF

cat >"${REDIS_ACL}" <<EOF
user default off
user travel_agent on >${REDIS_PASSWORD} ~travel-agent:* +get +set +del +expire +scan +watch +unwatch +multi +exec +ping
user travel_agent_admin on >${REDIS_ADMIN_PASSWORD} ~travel-agent:* +get +set +del +expire +scan +watch +unwatch +multi +exec +ping +bgsave +lastsave +info
EOF

chmod 0600 "${ENV_FILE}"
chown root:999 "${REDIS_ACL}"
chmod 0640 "${REDIS_ACL}"
chown 999:999 /srv/travel-agent/data/redis

echo "Server secrets and Redis ACL created without printing credential values."

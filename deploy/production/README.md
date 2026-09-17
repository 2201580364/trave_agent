# Travel Agent 镜像与挂载部署

关联：G7-R0.3、H3。服务器只拉取本地构建并推送的镜像，不上传应用源码。实际发布状态、验收结果和待办见 [CURRENT](../../docs/process/CURRENT.md)。

## 配置与数据目录

Compose 入口为 `/opt/travel-agent/infra/docker-compose.yml`。生产部署不使用 `env_file`，也不需要 `--env-file`；端口、资源限制和镜像 digest 在 Compose 中修改。API 与迁移只有一个非秘密环境变量 `TRAVEL_AGENT_CONFIG_FILE`，它指定只读挂载文件路径。

| 服务 | 宿主机配置 | 日志 | 持久数据 |
|---|---|---|---|
| API | `/etc/travel-agent/api/.env` | `/srv/travel-agent/logs/api/` | `/srv/travel-agent/data/api/`；只读 published 目录 |
| migrate | `/etc/travel-agent/migrate/.env` | `/srv/travel-agent/logs/migrate/migrate.log` | 使用同一 MySQL，迁移账户独立 |
| edge | `/etc/travel-agent/edge/Caddyfile` | `/srv/travel-agent/logs/edge/` | `/srv/travel-agent/data/edge/` |
| user-h5 | `/etc/travel-agent/user-h5/Caddyfile` | `/srv/travel-agent/logs/user-h5/` | `/srv/travel-agent/data/user-h5/` |
| admin-web | `/etc/travel-agent/admin-web/Caddyfile` | `/srv/travel-agent/logs/admin-web/` | `/srv/travel-agent/data/admin-web/` |
| MySQL | `/etc/travel-agent/mysql/conf.d/travel-agent.cnf`；客户端认证在 `mysql/clients/` | `/srv/travel-agent/logs/mysql/` | `/srv/travel-agent/data/mysql/` |
| Redis | `/etc/travel-agent/redis/redis.conf`、`users.acl`；健康/备份认证文件同目录 | `/srv/travel-agent/logs/redis/` | `/srv/travel-agent/data/redis/` |

数据库与发布数据目录沿用既有路径，禁止 `down -v`、清空或重新初始化。API 和迁移任务分别精确只读挂载一个 `.env` 文件，不把整个配置目录暴露给容器。配置文件必须在启动前预建，不能依靠 Docker 自动创建空目录或文件。

## 管理员与高德配置

编辑 `/etc/travel-agent/api/.env`，格式参考项目根 `.env.example`。使用与本地相同的 `KEY=value` 格式和 `TRAVEL_AGENT_*` 名称，完整配置项与说明以项目根 `.env.example` 为唯一模板。该文件是生产运行配置的权威来源，会覆盖同名进程值；不会再搜索其他 `.env`。文件缺失、语法错误、非法键会明确失败且不回显内容。文件修改后需重启相应容器，不提供自动热加载。

```dotenv
TRAVEL_AGENT_ADMIN_BOOTSTRAP_LOGIN = "your-admin-login"
TRAVEL_AGENT_ADMIN_BOOTSTRAP_PASSWORD = "replace-on-server"
TRAVEL_AGENT_GAODE_API_KEY = "replace-on-server"
```

管理员 bootstrap 仅用于管理员表为空时首次创建，不能用它重置已有账户密码。不要用以上片段覆盖整个文件，保留数据库、签名密钥和 published 路径等配置。迁移凭证只写入 migrate 配置，不赋予 API DDL 权限。

```bash
sudoedit /etc/travel-agent/api/.env
sudo docker compose -f /opt/travel-agent/infra/docker-compose.yml restart api
curl -fsS http://127.0.0.1:18080/health/ready
```

本地开发继续使用项目根 `.env`，不需要部署配置文件。真实 .env、ACL、客户端认证和密码文件不提交 Git、不进镜像层。

## 数据库认证与权限

API/migrate 配置目录和文件分别为 `root:10001 0750/0640`，API 日志与运行数据由 UID 10001 写入。MySQL/Redis 日志和数据按现有 UID 999 管理；配置文件 `root:999 0640`，目录 0750。Caddy 配置无秘密，日志目录仅服务用户可写。

MySQL `clients/` 保存 `health.cnf`、`backup.cnf`、`root.cnf`、`root-password`、`database`；认证文件使用 `[client]` 原生格式。初始化只传递 `MYSQL_ROOT_PASSWORD_FILE` 路径；已有库的账户密码不会因编辑文件自动变化。修改数据库或 Redis 账号密码时，必须同时更新服务侧账号/ACL以及对应 API、迁移、健康检查和备份认证，不可只改客户端密码。

Redis 的 `health-user/health-password` 用于健康检查，`admin-user/admin-password` 用于备份；ACL 仍是服务侧权威。密码经文件读取，不放入 Compose、命令参数或 Docker 的配置环境变量中。

## 更新与迁移

1. 本地按锁定依赖运行测试，构建 linux/amd64 镜像，推送授权仓库并记录 digest。
2. 服务器先保留旧 Compose/配置和已校验备份；只上传明确的部署配置和运维脚本。
3. 更新 Compose digest；执行 `docker compose -f /opt/travel-agent/infra/docker-compose.yml config --quiet` 与 `pull`。
4. 需要迁移时，先运行 `sudo bash /opt/travel-agent/infra/scripts/run-migrations.sh --dry-run`，再用 `--apply`。迁移日志写入宿主机，失败时不继续发布。
5. 执行 `up -d`；检查 readiness、容器健康、业务页面、挂载日志以及备份。

## 备份、日志与回滚

`backup.sh` 默认只预览；`--apply` 使用挂载的 MySQL 只读备份账号和 Redis 管理账号，生成 gzip/RDB 与 SHA-256 清单。定时服务使用相同入口，不再读取 `infra.env`。备份文件写 `/srv/travel-agent/backups/`；不自动删除历史备份，需监控容量并按删除纪律处理保留期。

```bash
sudo bash /opt/travel-agent/infra/scripts/backup.sh --dry-run
sudo bash /opt/travel-agent/infra/scripts/backup.sh --apply
```

API 日志按日期与等级分文件，完成月份归档；Caddy 文件按 20MiB 轮转保留 10 份。Docker stdout 同样限制 20MiB × 10；MySQL/Redis/迁移文件用宿主机 logrotate 配置管理。数据库审计记录仍存储在 MySQL，不作为普通日志导出。

回滚时恢复本次切换前保存的 Compose 和配置，使用原 digest；不以回滚应用为由覆盖数据库。旧 `app.env/migrate.env/infra.env` 仅在新配置、备份、日志、健康验证后按逐路径确认清理。旧 provision/validate 脚本依赖 env 的入口属于历史流程，不得在挂载部署上执行；保留到删除清单确认后移除。`restore-drill.sh` 使用备份文件，不依赖旧 env，但会创建并清理临时容器/卷，执行前按项目规则核对副作用。

迁移配置时复制所需的 `.env` 配置项，并调整数据库/Redis 地址与容器内路径；不要把本地 SQLite 路径直接用于服务器。

# Travel Agent Docker Compose 部署包

本目录当前实现 Redis/MySQL 基础设施 Compose，G7-R0.3 将按 [`../../docs/ops/gate7-controlled-h5-docker-deployment.md`](../../docs/ops/gate7-controlled-h5-docker-deployment.md) 扩展为 edge/H5、FastAPI、迁移任务、MySQL、Redis 统一 Docker 镜像部署和 Docker Compose 管理。真实凭证由服务器脚本生成并保存在 `/etc/travel-agent/`，不会回显或提交到 Git。

统一部署原则：服务器宿主机不直接运行 FastAPI、Node、Nginx/Caddy、MySQL 或 Redis；除 Docker Engine、Docker Compose、必要安全参数和备份调度外，所有常驻应用组件均由一个逻辑 Compose 项目管理。当前 `name: travel-agent-infra` 是已验收的过渡基线，应用层实施时再评审迁移为 `name: travel-agent`，本轮不修改正在运行的服务器栈。

## Git 提交边界

本目录应提交的内容只有可复现的无凭证基线：

```text
docker-compose.yml
infra.env.example
mysql/redis 无凭证配置
scripts/ 部署、迁移、备份和恢复脚本
validation/ 无凭证真实服务验收脚本
systemd/ 定时备份单元
sysctl/ Redis 宿主机参数
README.md
```

以下内容由根 `.gitignore` 明确排除，禁止提交：

```text
infra.env / app.env / .env*
Redis users.acl
MySQL/Redis data 目录
数据库备份、SQL dump、RDB、AOF
服务器上传归档和本机 .local 临时目录
SSH 私钥、PEM、PPK
```

## 服务器目录

```text
/opt/travel-agent/infra/             Compose 与无凭证配置
/etc/travel-agent/infra.env          root:root 0600 服务凭证
/etc/travel-agent/redis/users.acl    root:999 0640 Redis ACL（父目录 root:root 0750）
/srv/travel-agent/data/mysql/        MySQL InnoDB 数据
/srv/travel-agent/data/redis/        Redis AOF/RDB 数据
/srv/travel-agent/backups/mysql/     MySQL 逻辑备份
/srv/travel-agent/backups/redis/     Redis RDB 备份
```

服务器盘点发现已有业务占用 3306，因此 Travel Agent 使用独立回环端口 `127.0.0.1:13306`（MySQL）与 `127.0.0.1:16379`（Redis），不向公网开放。后续应用若也通过 Compose 部署，应加入 `travel-agent-backend` 网络并使用服务名 `mysql`、`redis`；不得为了方便直接向公网开放数据库端口。Compose 只向 MySQL 注入初始化所需的 MySQL 变量，只向 Redis 健康检查注入受限应用 ACL 用户与密码，不把两套服务的全部凭证交叉注入容器。

当前服务器为 4 vCPU、约 3.6 GiB 内存，且已有两个 MySQL、一个 Redis 和一个 API 容器。为隔离资源影响，Travel Agent MySQL 使用 256 MiB buffer pool、50 个最大连接和 768 MiB 容器内存上限；Redis 使用 128 MiB `maxmemory`、`noeviction` 和 192 MiB 容器内存上限。扩容或迁移到独立服务器后必须根据真实负载重新评估，而不是永久沿用当前小规格参数。

宿主机安装 `/etc/sysctl.d/99-travel-agent-redis.conf` 并设置 `vm.overcommit_memory=1`，避免 Redis 在 BGSAVE/AOF rewrite 时因 fork 内存检查失败。该参数对同机其他 Redis 同样生效；部署后必须通过 `sysctl vm.overcommit_memory` 和一次真实备份验证。

## 部署顺序

以下命令只允许在用户提供并授权的服务器执行：

```text
sudo install -d -m 0755 /opt/travel-agent/infra
上传本目录内容到 /opt/travel-agent/infra
sudo bash /opt/travel-agent/infra/scripts/provision-secrets.sh
sudo bash /opt/travel-agent/infra/scripts/provision-app-env.sh
sudo docker compose \
  --env-file /etc/travel-agent/infra.env \
  -f /opt/travel-agent/infra/docker-compose.yml \
  up -d
等待两个容器 healthy
sudo bash /opt/travel-agent/infra/scripts/provision-mysql-users.sh
sudo bash /opt/travel-agent/infra/scripts/provision-mysql-backup-user.sh
sudo bash /opt/travel-agent/infra/scripts/run-migrations.sh
sudo bash /opt/travel-agent/infra/scripts/validate-services.sh
sudo bash /opt/travel-agent/infra/scripts/validate-persistence.sh
sudo bash /opt/travel-agent/infra/scripts/validate-redis-runtime.sh
sudo bash /opt/travel-agent/infra/scripts/validate-service-recovery.sh
```

`/etc/travel-agent/app.env` 为 `root:root 0600`，只保存应用 DML 账号的 MySQL URL、Redis 受限 ACL URL和连接池参数；不包含迁移账号。之后使用迁移脚本临时构造迁移账号 URL运行 Alembic，应用运行时只加载 `app.env`。服务器验收必须覆盖 Redis ACL、MySQL 最小权限、InnoDB 并发、断连恢复、备份和隔离恢复，不能只检查容器处于 running。

## 备份

```text
sudo bash /opt/travel-agent/infra/scripts/backup.sh
```

脚本使用独立只读 MySQL backup 账号生成 gzip 逻辑备份，并生成 Redis RDB 和 SHA-256 校验文件，默认保留 14 天。当前 schema 不使用存储过程；若未来引入 routines，必须评审 `SHOW_ROUTINE` 权限并更新恢复门禁，不能静默遗漏。正式定时任务和异地备份只在服务器部署验证后启用。

服务器通过 `travel-agent-infra-backup.timer` 每天北京时间 03:30 执行备份，并随机延迟最多 15 分钟以避开固定负载尖峰。Timer 使用 `Persistent=true`，关机错过执行窗口后会在下次启动补跑。当前只保存同机备份；在配置对象存储或第二服务器前，不得将其描述为异地容灾。

每次备份完成后，必须在不连接生产端口、使用一次性容器和一次性 Docker Volume 的隔离环境执行恢复演练：

```text
sudo bash /opt/travel-agent/infra/scripts/restore-drill.sh
```

也可以显式传入 `/srv/travel-agent/backups/checksums-<timestamp>.sha256`。脚本先校验 SHA-256，再分别恢复 MySQL 与 Redis，检查 MySQL 表数量、Alembic revision 和 Redis 可读性，最后删除一次性容器与 Volume；它不会覆盖生产数据目录。异地副本、备份加密和正式定时任务仍需在服务器资源与备份目标确认后启用。

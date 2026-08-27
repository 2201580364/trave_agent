# MySQL 预发布部署与验证清单

- 文档日期：2026-08-28
- 适用阶段：A6-8.2 真实 MySQL、部署与恢复
- 当前状态：真实 MySQL 8.0.46 已通过 Docker Compose 独立部署；Alembic 0001/0002、最小权限、InnoDB 并发、中文/emoji/JSON/时区、事务回滚、断连恢复、备份和隔离恢复均已验证

## 0. 环境边界

- 禁止在开发本机安装、启动或部署测试 MySQL、MariaDB 或 Redis 服务；
- 真实数据库安装、建库、迁移、并发事务、TLS、备份恢复和故障演练只在用户明确提供并授权的服务器上执行；
- 本机只允许不启动真实数据库服务的模型、迁移脚本静态检查和 SQLite 单元测试；这些结果不得冒充真实 InnoDB 证据；
- 未获得服务器地址、SSH 授权、网络边界和备份位置前，不猜测主机、账号、端口或凭证，也不对系统现有服务进行探测性写入。

## 1. 版本与存储要求

- MySQL 8.0；当前迁移使用 `utf8mb4_0900_ai_ci`，不将 MariaDB 视为等价替代；
- 默认存储引擎为 InnoDB；
- 数据库、连接和表字符集统一为 `utf8mb4`；
- 应用驱动为 PyMySQL，SQLAlchemy URL 使用 `mysql+pymysql://`；
- 生产时间统一以带时区 ISO-8601 字符串或快照字段保存，禁止依赖服务器本地时区推断业务时间。

## 2. 网络与账号

- MySQL 只监听 localhost、内网地址或受控私有网络；禁止直接向公网开放 3306；
- 迁移账号与应用运行账号分离；
- 应用账号只授予当前数据库的 `SELECT/INSERT/UPDATE/DELETE`；
- 迁移账号按需授予 `CREATE/ALTER/INDEX/DROP`，不得作为长期应用账号；
- 禁止使用 root 账号运行应用；
- 密码不得提交到 Git、Alembic 配置、日志、测试快照或错误响应。

示例权限仅供管理员按实际库名调整：

```sql
CREATE DATABASE travel_agent
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_0900_ai_ci;

CREATE USER 'travel_agent_app'@'<application-host>' IDENTIFIED BY '<secret>';
GRANT SELECT, INSERT, UPDATE, DELETE
  ON travel_agent.* TO 'travel_agent_app'@'<application-host>';
```

## 3. 应用配置

本地开发可在仓库根目录 `.env` 配置；真实 `.env` 已被 Git 忽略，仓库只提交 `.env.example`。生产环境仍应通过 Secret、容器或服务管理器注入同名环境变量，并覆盖 `.env`：

```text
TRAVEL_AGENT_DATABASE_URL=mysql+pymysql://<user>:<password>@<host>:3306/travel_agent
TRAVEL_AGENT_DATABASE_ECHO=false
TRAVEL_AGENT_DB_POOL_SIZE=5
TRAVEL_AGENT_DB_MAX_OVERFLOW=10
TRAVEL_AGENT_DB_POOL_RECYCLE_SECONDS=1800
TRAVEL_AGENT_DB_POOL_TIMEOUT_SECONDS=30
```

密码包含 `@`、`:`、`/`、`%` 等字符时必须进行 URL 编码。不得把真实连接串写入 `.env.example` 或 `alembic.ini`；应用与 `migrations/env.py` 会加载本地 `.env`，进程环境中的 `TRAVEL_AGENT_DATABASE_URL` 优先级更高。

## 4. 首次迁移

在空的预发布数据库执行：

```text
alembic upgrade head
```

预期 revision：

```text
0002_anonymous_identity
```

迁移后 `/health/ready` 必须同时满足：

```text
database = true
migration = true
current_revision = expected_revision
```

禁止在生产应用启动时静默自动执行破坏性迁移。迁移应作为独立部署步骤运行并保留输出。

## 5. 必须执行的真实 MySQL 验证

1. 空库执行 `upgrade head`；
2. 保存并恢复中文、emoji、跨午夜时间和长 JSON 快照；
3. 两个独立数据库连接同时领取同一 queued Intent，确认只有一个条件 UPDATE 成功；
4. 完成事务中途制造异常，确认 SolverRun、Trip、Revision、Intent 不留下半成品；
5. 重启 API 进程，确认 Draft、Intent 和 Revision 可恢复；
6. 断开并恢复 MySQL，验证 `pool_pre_ping` 和连接池回收；
7. 检查慢查询和索引使用；
8. 验证应用账号不能 CREATE/DROP/GRANT；
9. 验证迁移账号不被应用进程使用；
10. 执行备份与恢复演练，而不只是生成备份文件。

## 6. 备份与恢复

- 至少每日逻辑或物理备份；
- 备份文件加密并保存在不同故障域；
- 明确保留周期、恢复点目标和恢复时间目标；
- 每月至少抽样恢复到隔离环境；
- 恢复后运行 Alembic revision、行程守恒和 Revision 哈希检查；
- 删除或覆盖备份前必须确认存在另一份可恢复副本。

## 7. 当前未完成边界

- 正式发布数据表和数据库 PublishedDataProvider 尚未实现；
- FastAPI 生产服务尚未部署，未执行真实用户流量容量和慢查询/索引压测；
- 本项目 MySQL 仅绑定 loopback，同机访问不启用跨主机 TLS；未来跨主机前必须补私网/VPN + TLS；
- 每日同机备份已经启用，但尚无对象存储/第二故障域和备份加密；
- 尚无集中指标、告警和值班通知；
- 同机既有非本项目 MySQL 暴露 0.0.0.0:3306 且 UFW inactive，未获授权不得修改，服务器所有者必须独立核查云安全组；
- 详细真实证据见 `docs/test/reports/a6-8-2-server-mysql-redis-validation-2026-08-28.md`。

## 8. 开始服务器部署前需要的信息

建议使用 SSH Key，不要在对话、Git、命令参数或日志中直接发送明文密码。开始部署至少需要：

```text
服务器公网/内网地址或已配置 SSH Host 别名
SSH 端口
部署用户
SSH 私钥在本机的路径，或已可用的 ssh-agent/系统凭证
该用户是否具有 sudo 权限
服务器操作系统及版本
允许访问 MySQL/Redis 的应用服务器来源 IP 或网段
MySQL、Redis 是新安装还是复用已有服务
TLS 证书来源或内部 CA 约定
备份目标位置、保留周期和允许的恢复演练窗口
```

真实数据库密码、Redis ACL 密码和应用连接串应在服务器 Secret、受限配置文件或 Git 已忽略的 `.env.server` 中提供，不得提交到仓库。

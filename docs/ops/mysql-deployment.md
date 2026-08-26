# MySQL 预发布部署与验证清单

- 文档日期：2026-08-25
- 适用阶段：A6-6.5 之后、A6-7 前端正式联调之前
- 当前状态：方言与配置准备完成，真实 MySQL 服务端验证尚未执行

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

- 尚未连接真实 MySQL Server；
- 尚未验证真实 InnoDB 并发事务；
- 尚未完成正式发布数据表和数据库 Provider；
- 尚未完成 TLS、服务器防火墙、备份任务和监控；
- 尚未执行生产容量、慢查询和故障恢复验证。

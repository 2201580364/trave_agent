# A6-8.2 服务器 MySQL/Redis 部署与恢复验证报告

- 日期：2026-08-28
- 阶段：M1 / A6-8.2
- 环境：用户授权的腾讯云 Ubuntu 24.04.4 LTS CVM
- 结论：Travel Agent 独立 MySQL/Redis 基础设施部署与核心恢复验收通过；外网应用发布、异地备份、集中监控和同机既有公网 3306 风险不在本次完成范围

## 1. 服务器盘点与隔离决策

服务器资源：

```text
4 vCPU（AMD EPYC 7K62）
内存约 3.6 GiB，Swap 约 1.9 GiB
系统盘 40 GiB，部署前可用约 24 GiB
Docker 29.1.3
Docker Compose 2.40.3
```

盘点发现服务器已运行两个非本项目 MySQL、一个 Redis 和一个 API 容器。其中一个既有 MySQL 将宿主机 3306 绑定至 `0.0.0.0`，且 UFW 未启用。为避免破坏现有业务，本次没有停止、修改、复用或读取这些容器的凭证和数据。

Travel Agent 使用完全独立的：

```text
Compose project: travel-agent-infra
Docker network: travel-agent-backend
Containers: travel-agent-mysql / travel-agent-redis
Host ports: 127.0.0.1:13306 / 127.0.0.1:16379
Data: /srv/travel-agent/data/mysql /srv/travel-agent/data/redis
Backup: /srv/travel-agent/backups/mysql /srv/travel-agent/backups/redis
Secrets: /etc/travel-agent/infra.env /etc/travel-agent/app.env
```

## 2. 容量与运行参数

考虑同机已有负载，本次采用保守参数：

| 服务 | 参数 | 值 |
|---|---|---:|
| MySQL | image | mysql:8.0，实际 8.0.46 |
| MySQL | InnoDB buffer pool | 256 MiB |
| MySQL | max connections | 50 |
| MySQL | container memory limit | 768 MiB |
| Redis | image | redis:7.4-alpine |
| Redis | maxmemory | 128 MiB |
| Redis | eviction | noeviction |
| Redis | container memory limit | 192 MiB |

稳定状态观测：MySQL 约 371 MiB，Redis 约 3.3 MiB，均未触发容器限制。宿主机安装 `vm.overcommit_memory=1` 后，Redis 重启日志不再出现 BGSAVE/AOF fork 风险警告。

## 3. 认证、权限与网络验收

以下真实服务检查通过：

- MySQL 8.0.46、InnoDB、`utf8mb4`、`utf8mb4_0900_ai_ci`、UTC；
- 应用账号可以 SELECT/INSERT/UPDATE/DELETE，不能 CREATE；
- 迁移账号可执行 Alembic 所需 CREATE/ALTER/DROP；
- 应用运行环境只保存应用 DML URL，不包含迁移账号；
- Redis 默认用户关闭，应用 ACL 用户只允许 `travel-agent:*`；
- Redis 应用 ACL 可以 GET/SET/DEL/EXPIRE/SCAN/WATCH/MULTI/EXEC/PING；
- Redis 应用 ACL 不能访问其他前缀，不能执行 CONFIG 等管理命令；
- 13306 和 16379 均只监听 `127.0.0.1`；
- MySQL/Redis 密码和完整 URL未写入 Git、测试输出或本报告。
- 部署结束后，本机两个权限收紧的私钥工作副本和服务器 `/tmp` 上传副本均已删除；根目录原始私钥仍被 Git 明确忽略且未被追踪。

## 4. Alembic 与真实 InnoDB 持久化

空库升级成功：

```text
0001_planning_core
→ 0002_anonymous_identity (head)
```

真实 MySQL 应用验收通过：

- 中文、emoji、JSON、跨午夜和 Asia/Shanghai 带时区字符串往返一致；
- 新 Engine/Session 重新读取 Draft 与 Intent，领域值未丢失；
- 两个独立 MySQL 连接并发领取同一 queued Intent，恰好一个成功、一个 status conflict；
- 事务中途故意抛错后，未提交 Trip 不留残余；
- 受控停止 MySQL 时应用连接显式失败；
- 启动后同一启用 `pool_pre_ping` 的 Engine 恢复连接；
- 重启前已提交数据仍然存在；
- 所有 `validation_*` 验证记录在 finally 中清理。

## 5. 真实 Redis 治理与缓存

真实 Redis 验收通过：

- 10 个独立 Redis 连接并发申请治理请求槽，request/success 计数均无丢失；
- 两个客户端共享连续失败阈值和 CIRCUIT_OPEN；
- `rate_limited` 立即打开共享熔断；
- 一个客户端写入高德路线缓存，另一个客户端直接复用；
- 路线 Redis key 使用 SHA-256，不含明文坐标；
- Redis 状态不含 API Key、密码、完整 Redis URL或专属 Host；
- 受控停止 Redis 时客户端显式失败，未退回本地服务；
- 启动后同一 Redis 客户端恢复连接，AOF/RDB 数据仍存在；
- 所有 `travel-agent:validation:*` 验证键已清理。

该证据证明真实 Redis 的跨连接事务和持久化语义；尚未使用两台物理发布机器做网络分区测试，不能扩大解释为多机容灾已经完成。

## 6. 备份与隔离恢复

`backup.sh` 已在真实环境执行：

- MySQL 使用独立只读 backup 账号执行 single-transaction、events、triggers、hex-blob、no-tablespaces 的 gzip 逻辑备份；当前 schema 不含存储过程，未来若引入 routines 必须单独评审 `SHOW_ROUTINE`；
- Redis BGSAVE 必须在 60 秒内生成新的成功快照；超时会失败，不复制旧 RDB；
- 两类备份均生成 SHA-256；
- 文件权限为 root:root 0600；
- 失败时清理 `.partial` 文件；
- 同机保留周期为 14 天。

隔离恢复演练通过：

```text
SHA-256: MySQL OK / Redis OK
MySQL restored tables: 7
Alembic revision: 0002_anonymous_identity
Redis RDB load: success
```

恢复使用一次性容器和一次性 Docker Volume，未连接或覆盖生产数据目录；演练结束后临时容器与 Volume 均已删除。

`travel-agent-infra-backup.timer` 已启用，每天北京时间 03:30 执行，并随机延迟最多 15 分钟，`Persistent=true`。当前没有对象存储或第二服务器，因此仍是同故障域备份，不等同于异地容灾。

## 7. 日志与运行状态

最终状态：

```text
travel-agent-mysql: running / healthy / restart=unless-stopped
travel-agent-redis: running / healthy / restart=unless-stopped
backup timer: enabled / active
root filesystem: 42% used
restore containers/volumes: none
```

MySQL 日志中的可解释警告：

- 自动生成的 CA 为 self-signed；当前只监听 loopback，不用于跨主机 TLS；
- pid-file 容器目录权限提示；
- 故障演练主动停止容器时强制关闭测试连接；
- `skip-host-cache` 弃用提示需在后续镜像/配置升级时处理。

Redis overcommit 警告已通过宿主机 sysctl 修复，重启后未复现。

## 8. 遗留风险与下一门禁

| 风险 | 级别 | 处理 |
|---|---|---|
| 同机既有非本项目 MySQL 暴露 `0.0.0.0:3306`，UFW inactive | 高 | 未经授权不修改；必须由服务器所有者核对腾讯云安全组并收紧既有服务 |
| 当前 MySQL/Redis 无跨主机 TLS | 中 | 本项目只绑定 loopback；若应用移到其他服务器，必须先建设私网/VPN + TLS，不得开放公网端口 |
| 备份只在同一系统盘 | 高 | 接入对象存储或第二故障域后加密复制，并执行异地恢复 |
| 无集中指标、告警和值班通知 | 中 | 补容器健康、磁盘、备份失败、MySQL连接/慢查询、Redis内存/拒绝写告警 |
| Docker image 仅固定主/次版本标签，未固定 digest | 中 | 发布流水线增加镜像 digest 审核和升级窗口 |
| Python 依赖按版本范围现场解析，无生产 lock | 中 | 建立 Python 生产锁文件/制品构建，避免不同部署时间解析到不同版本 |
| 未执行真实用户流量容量和慢查询压测 | 中 | 应用服务部署后按匿名规划闭环压测并检查索引/慢查询 |
| 未用两台物理发布机器做网络分区/共享治理验证 | 中 | 有第二发布节点后补多机故障测试 |

## 9. 阶段结论

A6-8.2 的“真实 MySQL、真实 Redis、最小权限、Alembic、并发事务、断连恢复、备份与隔离恢复”范围已完成。该结论不表示：

- FastAPI/Taro 已作为公网生产服务发布；
- M1 产品功能已完整；
- Gate 7 专家/用户验证已通过；
- 异地容灾、集中监控或跨主机 TLS 已完成。

下一步应进入 M1 产品闭环缺口收口和应用服务发布准备，而不是继续无限打磨求解器或直接进入 M2。

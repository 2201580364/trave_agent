# Redis 跨机器 Provider 治理部署与验证清单

- 文档日期：2026-08-28
- 适用阶段：A6-8.1 正式部署验证
- 当前状态：真实 Redis 7.4 已通过 Docker Compose 独立部署；ACL、并发计数、共享熔断、跨客户端路线缓存、断连恢复、AOF/RDB、备份和隔离恢复均已验证

## 0. 环境边界

- 禁止在开发本机安装、启动或部署测试 Redis/MySQL 服务；
- Redis 安装、认证、TLS、ACL、网络访问、监控和故障演练只在用户明确提供并授权的服务器上执行；
- 未获得服务器和权限信息前，不读取系统现有 Redis 密码，不向未知 Redis 写测试键；
- fakeredis 只证明接口和事务语义，不替代真实 Redis、网络、认证、持久化和故障恢复证据。

## 1. 部署用途

M1 Redis 只承担发布前基础设施状态，不进入用户点击“生成行程”的实时求解路径：

```text
Provider 治理状态
→ 高德/和风按日安全预算
→ 跨机器最小请求间隔
→ 成功/失败分类
→ 连续失败与限流熔断

高德路线缓存
→ 成功路线的模式、耗时、距离、抓取时间和 TTL
```

Redis 不保存 API Key、和风专属 Host、Redis URL、TripRevision、用户身份、旅行小记或 Published Snapshot 本体。

## 2. 服务器和网络要求

- Redis 7.x；不使用开发本机服务；
- 仅监听服务器内网或受控私有网络地址；禁止直接向公网开放 6379；
- 使用 TLS，或在可信私网/VPN/SSH 隧道内传输；
- 使用专用 ACL 用户，只允许项目所需前缀和命令；
- 应用发布节点来源 IP/网段加入防火墙白名单；
- 配置内存上限、淘汰策略和指标监控；
- 明确 RDB/AOF、备份和故障切换策略，不把缓存持久化误当作业务数据库备份。

## 3. 建议 ACL 边界

项目需要的命令范围包括：

```text
GET / SET / DEL / EXPIRE
SCAN
WATCH / UNWATCH / MULTI / EXEC
PING
```

键范围限定为：

```text
<prefix>:provider-governance:*
<prefix>:gaode-route:*
```

不得授予 `FLUSHALL`、`FLUSHDB`、`CONFIG`、`MODULE`、`SCRIPT KILL`、复制拓扑管理等无关高危权限。

## 4. 应用配置

真实连接信息只写入服务器 Secret 或 Git 已忽略的 `.env.server`：

```dotenv
TRAVEL_AGENT_PROVIDER_REDIS_URL=rediss://<acl-user>:<secret>@<private-host>:<port>/<db>
TRAVEL_AGENT_PROVIDER_REDIS_PREFIX=travel-agent
```

日志、状态脚本和测试报告不得回显完整 URL。配置 Redis URL 后，Provider 治理与高德路线缓存同时使用 Redis；认证或连接失败必须终止发布构建，不得静默退回本机 JSON。

## 5. 真实服务器验收

1. 使用受限 ACL 用户执行 `PING`；
2. 两个独立进程同时申请请求槽，验证最小间隔和预算计数不会丢失；
3. 连续制造可控 timeout/http_error，验证达到阈值后两个进程都看到同一熔断状态；
4. 制造 `rate_limited`，验证立即熔断；
5. 两个进程共享同一高德路线缓存，第二个进程不调用 Provider；
6. 检查 Redis key 不包含明文坐标、API Key、Redis 密码和专属 Host；
7. 断开 Redis，验证构建显式失败且不会退回 JSON；
8. 恢复 Redis，验证熔断和预算状态按既定 TTL 恢复；
9. 验证 ACL 用户不能访问其他前缀、不能执行高危管理命令；
10. 验证 TLS、证书校验、监控告警、内存阈值和持久化策略。

## 6. 开始部署前需要的信息

```text
服务器地址或 SSH Host 别名
SSH 端口、部署用户、SSH Key/ssh-agent 授权
sudo 权限范围
服务器操作系统及版本
Redis 新装或复用现有服务
允许访问 Redis 的发布节点 IP/网段
TLS 证书或内部 CA 方案
Redis 数据目录、备份位置和监控系统
期望的 ACL 用户名、逻辑库和 key prefix
允许执行断连/恢复演练的时间窗口
```

优先使用 SSH Key。不要在对话、Git、命令参数或日志中发送明文服务器密码、Redis ACL 密码或完整连接 URL。

## 7. 已完成与遗留边界

- 10 个独立真实 Redis 连接并发计数无丢失；阈值熔断、`rate_limited` 立即熔断和跨客户端路线缓存通过；
- ACL 键前缀与命令限制通过；路线 key 不含明文坐标，状态不含凭证；
- 受控断连时客户端显式失败，重启后连接与 AOF/RDB 数据恢复；
- `vm.overcommit_memory=1` 已持久化，真实 BGSAVE 与备份通过；
- 当前只绑定 loopback，不为跨主机开放 6379；未来跨主机必须先补私网/VPN + TLS；
- 尚未使用两台物理发布机器执行网络分区和跨机器故障测试；
- 尚无集中配额看板、Redis 指标告警和异地备份；
- 详细真实证据见 `docs/test/reports/a6-8-2-server-mysql-redis-validation-2026-08-28.md`。

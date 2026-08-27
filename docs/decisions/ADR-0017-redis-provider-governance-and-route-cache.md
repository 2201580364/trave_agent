# ADR-0017：Redis 跨机器 Provider 治理与高德路线缓存

- **状态**：已接受
- **日期**：2026-08-28
- **决策者**：产品 + 工程
- **关联假设**：H3
- **前置**：ADR-0005、ADR-0010、ADR-0014、ADR-0016

## 背景

ADR-0016 和 A6-8.1 首轮治理实现已经提供本机/共享文件系统上的按日安全预算、请求间隔、熔断、JSON 路线缓存和旧 Published Snapshot 回退。该方案适合单机开发和单发布节点，但多个发布 Worker 分布在不同机器时，本地文件不能可靠共享配额计数、熔断状态或高德路线缓存，可能造成重复请求、突破项目侧安全预算，或让不同机器对 Provider 健康状态产生分歧。

跨机器共享不能通过静默扫描网络目录或在 Redis 故障时自动退回各自本地文件实现，否则多个实例会在故障期间形成彼此独立的预算和熔断状态。

## 决策

### D1 本地 JSON 与 Redis 使用同一治理语义

保留锁定 JSON 后端作为本地开发默认值；配置 `TRAVEL_AGENT_PROVIDER_REDIS_URL` 后，高德和和风快照脚本统一切换到 Redis：

```dotenv
TRAVEL_AGENT_PROVIDER_REDIS_URL=redis://:<password>@<host>:<port>/<db>
TRAVEL_AGENT_PROVIDER_REDIS_PREFIX=travel-agent
```

两个后端执行相同的按日安全预算、跨实例最小请求间隔、成功/失败分类、连续失败熔断、限流立即熔断和恢复窗口语义。

### D2 Redis 治理状态使用乐观事务

每个 Provider 使用独立键，更新通过 Redis `WATCH/MULTI/EXEC` 完成。并发写冲突必须重试，不能覆盖其他实例刚写入的请求计数或熔断状态。状态设置 90 天 TTL，只保存：

```text
quota_day / daily_request_budget / request_count
success_count / failure_count / failure_counts
consecutive_failures / last_request_at / circuit_open_until
```

不得保存 API Key、Redis 密码、专属 API Host、完整 URL 或请求参数。

### D3 高德路线缓存使用散列键和 Redis TTL

高德路线缓存键对坐标、模式、城市、数据版本和策略组成的规范化键执行 SHA-256，不把明文坐标或凭证放入 Redis key。缓存值只保存模式、耗时、距离、抓取时间和过期时间，并同时使用 Redis TTL。

不同机器连接同一 Redis 后复用成功路线；缓存命中不消耗 Provider 请求预算。

### D4 Redis 配置后故障必须显式失败

存在 `TRAVEL_AGENT_PROVIDER_REDIS_URL` 时，Redis 是该发布流程的共享一致性边界。连接失败、认证失败或事务失败必须阻止联网构建，不得静默退回本地 JSON，否则会失去跨机器预算和熔断一致性。

未配置 Redis URL 时才使用本地 JSON 后端。

### D5 Redis 状态提供凭证无关查看入口

`scripts/show_provider_governance.py` 自动识别 JSON/Redis 后端，输出人类可读或 JSON 状态。输出只包含 Provider 名称、预算、计数、失败分类和熔断时间，不显示连接 URL。

## 验证

- fakeredis 覆盖两个独立客户端共享预算、失败计数和熔断；
- fakeredis 覆盖两个客户端共享高德路线缓存，Redis key 不含明文坐标和凭证；
- Redis 和 MySQL 的服务部署与真实协议验证不得在开发本机进行；正式证据必须来自用户明确提供并授权的服务器；
- 2026-08-28 在该边界明确前曾进行一次短生命周期本机 Redis 协议检查，随后验证键、临时进程和临时目录均已清理；按新增边界，该结果不计入正式部署验收证据；
- 项目当前 `.env` 尚未配置授权服务器 Redis URL，因此尚未执行正式跨主机联调。

## 影响与后续

- 新增生产依赖 `redis>=4.6,<5`，与当前环境的既有任务依赖兼容；测试使用 `fakeredis`；
- A6-8.1 跨机器共享代码闭环已经完成；仍需在用户授权服务器的正式 Redis 上完成认证、TLS、ACL、网络边界、监控、备份策略和多实例故障演练；
- 本地安全预算不等于高德/和风控制台套餐配额，正式配额来源和集中告警仍需运维接入；
- Redis 不保存 Published Snapshot 本体和 TripRevision，正式发布表与业务持久化仍由 A6-8.2 MySQL 负责。

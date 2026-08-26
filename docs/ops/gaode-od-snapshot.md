# 高德真实 OD 快照构建与安全联调

- 状态：A6-8.1 离线实现完成，真实联网待部署环境验证
- 日期：2026-08-26
- 依据：ADR-0010、ADR-0011

## 1. 边界

高德 Web 服务只用于发布前构建版本化、有向 OD 快照。OR-Tools 求解过程不调用高德 HTTP，不把 API 延迟、配额或临时失败引入搜索循环。

常规单元测试、Golden Case、降级测试和本地开发默认不联网。真实请求必须同时满足：

1. 部署环境已设置高德 Web 服务 Key；
2. 操作者显式传入 `--execute-live`；
3. 输入文件中的每个景点均通过发布数据门禁并具有实际入口坐标；
4. 为本次快照提供新的、可追踪的 `--data-version`；
5. 输出文件进入发布审核流程后才可供生产组合根使用。

## 2. 凭证设置

不要在对话、命令历史、代码、配置文件或 Git 中保存 Key。仅在当前部署环境设置：

```powershell
$env:TRAVEL_AGENT_GAODE_API_KEY = "<在本机安全设置，不要提交>"
$env:TRAVEL_AGENT_GAODE_CITY_CODE = "330100"
$env:TRAVEL_AGENT_GAODE_TIMEOUT_SECONDS = "5"
$env:TRAVEL_AGENT_GAODE_CACHE_TTL_SECONDS = "86400"
$env:TRAVEL_AGENT_GAODE_MODES = "walking,transit,driving"
```

`GaodeSettings` 的 Key 字段不参与 `repr`；脚本不打印 Key。日志、审计和行程结果也不得保存 Key 或带 Key 的完整请求 URL。

## 3. 构建命令

不允许降级、要求所有有向边都来自高德：

```powershell
py -3.12 scripts/build_gaode_od_snapshot.py `
  --input tests/data/hangzhou_attractions_snapshot.json `
  --output var/published/gaode-hangzhou-2026-08-26-v1.json `
  --data-version gaode-hangzhou-2026-08-26-v1 `
  --execute-live
```

允许高德失败边透明使用近似 OD：

```powershell
py -3.12 scripts/build_gaode_od_snapshot.py `
  --input tests/data/hangzhou_attractions_snapshot.json `
  --output var/published/gaode-hangzhou-2026-08-26-v1.json `
  --data-version gaode-hangzhou-2026-08-26-v1 `
  --allow-approximate-fallback `
  --execute-live
```

第二种方式只适合受控降级。每条降级边都会保存 `basis=approximate` 和 `fallback_reason`；不能把该文件描述为“全量真实高德 OD”。

## 4. 输出检查

输出使用 `gaode-od-snapshot-v1`，包含：

```text
data_version
generated_at
city_code
enabled_modes
report.requested_pair_count
report.gaode_pair_count
report.fallback_pair_count
report.missing_pair_count
report.failure_counts
pairs[]
```

每条可用边包含：

```text
origin_id / destination_id
travel_min
travel_mode
distance_m
basis
data_version
fetched_at
fallback_reason
```

发布前必须检查：

- `requested_pair_count = N × (N - 1)`；
- 不允许降级时，`gaode_pair_count = requested_pair_count`；
- 允许降级时，所有 approximate 边均有原因；
- `missing_pair_count = 0`，否则脚本返回非零退出码；
- A→B 与 B→A 均存在且独立；
- 文件中不存在 Key；
- 入口坐标、数据版本和抓取时间可追溯；
- 抽样与高德网页/客户端路线进行人工比对，避免错误入口点或城市编码造成系统性偏差。

## 5. 当前未完成

- 尚未使用真实 Key 执行杭州快照构建；
- 尚未将生成的 JSON 接入正式发布数据表或生产组合根；
- 尚未建立跨进程/跨机器持久化缓存、配额看板和熔断状态；
- 尚未验证高德服务配额、TLS/代理、生产网络和故障恢复；
- 尚未完成真实餐厅节点加入后的全量 OD 重建与新 Revision 重排。

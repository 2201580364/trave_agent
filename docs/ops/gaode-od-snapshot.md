# 高德真实 OD 快照构建与安全联调

- 状态：A6-8.1 真实联网严格快照已验证；当前停止联网请求，使用快照离线回归
- 日期：2026-08-26
- 依据：ADR-0010、ADR-0011

## 1. 边界

高德 Web 服务只用于发布前构建版本化、有向 OD 快照。OR-Tools 求解过程不调用高德 HTTP，不把 API 延迟、配额或临时失败引入搜索循环。

常规单元测试、Golden Case、降级测试和本地开发默认不联网。真实请求必须同时满足：

1. 本地 `.env` 或部署环境已设置高德 Web 服务 Key；
2. 操作者显式传入 `--execute-live`；
3. 输入文件中的每个景点均通过发布数据门禁并具有实际入口坐标；
4. 为本次快照提供新的、可追踪的 `--data-version`；
5. 输出文件进入发布审核流程后才可供生产组合根使用。

## 2. 本地 `.env` 配置

仓库提供可提交的 `.env.example`，真实 `.env` 已由 `.gitignore` 排除。首次配置：

```powershell
Copy-Item .env.example .env
```

然后只在本机编辑 `.env`：

```dotenv
TRAVEL_AGENT_GAODE_API_KEY=<高德 Web 服务 Key>
TRAVEL_AGENT_GAODE_CITY_CODE=330100
TRAVEL_AGENT_GAODE_TIMEOUT_SECONDS=5
TRAVEL_AGENT_GAODE_CACHE_TTL_SECONDS=86400
TRAVEL_AGENT_GAODE_DATA_VERSION=gaode-hangzhou-local-v1
TRAVEL_AGENT_GAODE_MODES=walking,transit,driving
```

不要在对话、命令历史、代码、`.env.example` 或 Git 中保存真实 Key。应用通过 `python-dotenv` 显式加载仓库根目录 `.env`，且 `override=false`：Docker、CI/CD、服务管理器等已注入的环境变量优先于 `.env`，因此生产部署仍可以使用 Secret 管理而不依赖文件。

`GaodeSettings` 的 Key 字段不参与 `repr`；脚本不打印 Key。日志、审计和行程结果也不得保存 Key 或带 Key 的完整请求 URL。

提交前确认：

```powershell
git check-ignore -v .env
git status --short
```

`.env` 必须显示为已忽略，且不得出现在待提交文件中；`.env.example` 可以提交，但只能包含占位值。

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
report.failure_details
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

- 尚未将生成的 JSON 接入正式发布数据表或生产组合根；
- 已实现本机跨进程 JSON 持久化缓存，默认位于 Git 忽略的 `var/cache/gaode-routes.json`；尚未建立跨机器共享缓存、配额看板和熔断状态；
- 尚未验证高德服务配额、TLS/代理、生产网络和故障恢复；
- 尚未完成真实餐厅节点加入后的全量 OD 重建与新 Revision 重排。

## 6. 失败明细与持久化缓存

新构建报告除 `failure_counts` 聚合统计外，还保存脱敏后的 `failure_details[]`：

```text
origin_id / destination_id
mode
code
infocode
occurred_at
```

报告和缓存均不得保存 Key、带 Key 的 URL或完整请求参数。缓存键包含起终坐标、交通模式、城市编码、数据版本和路线策略；缓存值包含模式、耗时、距离、抓取时间和过期时间。写入使用临时文件替换，避免进程中断留下半个 JSON。

构建脚本默认复用：

```text
var/cache/gaode-routes.json
```

也可通过 `--cache` 显式指定。缓存只减少重复成功请求，不改变受控联网边界：没有 `--execute-live` 时脚本仍不得访问高德。当前配额已经触发 `rate_limited`，在高德控制台确认恢复前只允许使用既有快照和缓存做离线验证。

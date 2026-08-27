# 高德真实 OD 快照构建与安全联调

- 状态：A6-8.1 已完成真实坐标候选、请求节流、42/42 严格 OD 重建和 JSON 发布 Provider 技术验证；正式发布等待点位人工确认
- 日期：2026-08-26
- 依据：ADR-0010、ADR-0011、ADR-0012、ADR-0013

## 1. 边界

高德 Web 服务只用于发布前构建版本化、有向 OD 快照。OR-Tools 求解过程不调用高德 HTTP，不把 API 延迟、配额或临时失败引入搜索循环。

常规单元测试、Golden Case、降级测试和本地开发默认不联网。真实请求必须同时满足：

1. 本地 `.env` 或部署环境已设置高德 Web 服务 Key；
2. 操作者显式传入 `--execute-live`；
3. 输入文件中的每个景点均通过发布数据门禁并具有带点位语义的路线坐标；候选坐标只可在审计构建时显式放行；
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
  --request-interval-seconds 1.05 `
  --execute-live
```

允许高德失败边透明使用近似 OD：

```powershell
py -3.12 scripts/build_gaode_od_snapshot.py `
  --input tests/data/hangzhou_attractions_snapshot.json `
  --output var/published/gaode-hangzhou-2026-08-26-v1.json `
  --data-version gaode-hangzhou-2026-08-26-v1 `
  --request-interval-seconds 1.05 `
  --allow-approximate-fallback `
  --execute-live
```

第二种方式只适合受控降级。每条降级边都会保存 `basis=approximate` 和 `fallback_reason`；不能把该文件描述为“全量真实高德 OD”。

脚本默认在真正的缓存未命中请求之间至少等待 `1.05s`；命中持久化缓存不会等待。可以用 `--request-interval-seconds` 调整，但不能为了加快批量构建而绕过已确认的服务限流边界。

若输入记录的 `coordinate_review_status` 不是 `human_verified`，脚本默认拒绝。只有候选坐标审计允许显式传入：

```text
--allow-coordinate-candidates
```

带该标志生成的文件仍是候选证据，不能进入正式 production published 状态。

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

- 已实现不可变 JSON `PublishedSolverDataProvider`、正式快照、生产组合根、显式已知良好旧版本回退和生产回放；尚未迁入正式数据库发布表；
- 已实现本机跨进程 JSON 路由缓存和 Redis 跨机器路线缓存；Provider 治理同样支持 JSON/Redis 两种后端，包含按日安全预算、请求间隔、失败分类和熔断状态；
- 已在真实高德网络验证节流后完整构建不再触发限流；Redis 共享后端通过 fakeredis 双客户端单元测试，正式 Redis 协议、TLS/ACL/监控和多实例故障恢复只允许在用户提供并授权的服务器上验证；
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

也可通过 `--cache` 显式指定。缓存只减少重复成功请求，不改变受控联网边界：没有 `--execute-live` 时脚本仍不得访问高德。首轮无间隔诊断曾触发 `rate_limited`；按约 1.2 秒节流复查及使用默认 1.05 秒间隔完整重建后，所有有效请求均为 `infocode=10000`。

当前构建脚本已把缓存未命中请求接入持久化治理状态：

```dotenv
TRAVEL_AGENT_GAODE_DAILY_REQUEST_BUDGET=1000
TRAVEL_AGENT_PROVIDER_CIRCUIT_FAILURE_THRESHOLD=3
TRAVEL_AGENT_PROVIDER_CIRCUIT_OPEN_SECONDS=300
```

默认状态路径为 `var/ops/provider-governance.json`，可通过 `--governance-state` 指定。每日预算是项目侧安全上限，不等于或替代高德控制台套餐配额；生产值必须基于实际套餐配置并保留余量。查看状态：

```powershell
py -3.12 scripts/show_provider_governance.py
py -3.12 scripts/show_provider_governance.py --json
```

缓存命中不消耗请求预算；`rate_limited` 立即打开熔断，超时、HTTP、API 和无效响应按连续失败阈值打开熔断。短请求间隔只会等待到共享时间窗结束；每日预算耗尽和熔断打开会直接阻止继续联网，不会自动绕过治理或改用另一个 Key。

多机器发布节点必须配置同一个经过授权的 Redis：

```dotenv
TRAVEL_AGENT_PROVIDER_REDIS_URL=redis://:<password>@<host>:<port>/<db>
TRAVEL_AGENT_PROVIDER_REDIS_PREFIX=travel-agent
```

配置 Redis URL 后，治理状态和高德路线缓存同时切换到 Redis；连接或认证失败会终止构建，不会静默退回本地 JSON。Redis key 使用前缀隔离，路线 key 为 SHA-256，不包含明文坐标或凭证。正式环境应使用 TLS、最小权限 ACL、专用逻辑库/前缀、内存与淘汰监控，并验证断连和恢复流程。

环境边界：不得在开发本机安装、启动或部署测试 Redis/MySQL 服务。本地自动化只允许使用不监听网络端口的纯单元/仿真后端；真实 Redis 验收必须连接用户明确提供并授权的服务器。

## 7. 路线点与发布快照门禁

正式路线点不能只保存裸 `lat/lng`，至少需要：

```text
gaode_poi_id
routing_point_kind
coordinate_source
coordinate_fetched_at
coordinate_review_status
```

候选坐标文件与 OD 文件可通过 `scripts/build_candidate_published_solver_snapshot.py` 合并为审计 bundle。生成审计天气必须显式传入 `--acknowledge-audit-weather`；该天气固定标记为 `audit_normal_fixture`，不能宣称为实时天气。

`JsonPublishedSolverDataProvider` 加载 `published-solver-data-v1` 时校验 SHA-256、版本、景点 ID、外部 ID、天气日期、路线点来源、完整有向 OD、OD basis 和 OD data version。默认只加载 `status=published`，且正式坐标必须 `human_verified`；`allow_candidates=True` 仅供审计离线回放。

## 8. 2026-08-26 候选坐标严格重建结果

使用 7 个高德候选路线点、默认 1.05 秒请求间隔和严格模式完成真实重建，耗时约 132.8 秒：

```text
requested_pair_count = 42
gaode_pair_count     = 42
fallback_pair_count  = 0
missing_pair_count   = 0
mode_failures        = 4
```

最终模式为 driving 23、transit 15、walking 4；耗时范围 5–61 分钟，道路距离 324–11,587 米。4 次模式失败均为公交 `no_route / infocode=10000`，分别是灵隐寺↔飞来峰、西湖湖滨↔音乐喷泉；对应 OD 的其他模式成功，因此没有最终缺边。36 条有向边在耗时、距离或模式上与反向不同。

该快照及组合 bundle 位于 Git 忽略的 `var/audit/`，当前仅为 candidate。正式发布前仍需人工确认浙江省博物馆具体入口、灵隐寺/飞来峰联游入口和西湖湖滨开放区域代表点。

## 9. 生产组合根配置与启动

生产式 HTTP 应用不再由调用方手工注入内存 fixture，而是从环境显式选择唯一的 M1 城市发布快照：

```dotenv
TRAVEL_AGENT_PUBLISHED_SNAPSHOT_ROOT=./var/published
TRAVEL_AGENT_PUBLISHED_CITY_ID=hangzhou
TRAVEL_AGENT_PUBLISHED_SNAPSHOT_VERSION=hangzhou-published-YYYY-MM-DD-vN
```

启动命令：

```powershell
py -3.12 scripts/run_published_app.py --host 127.0.0.1 --port 8000
```

启动时 `build_production_http_app()` 会立即加载并校验指定快照，而不是等到用户提交生成请求后再发现数据问题。以下任一情况都会拒绝启动：

- root、城市或版本未显式配置；
- 文件不存在、版本名不安全或快照版本不一致；
- 快照仍为 `candidate`；
- 路线点未全部 `human_verified`；
- SHA-256、ID、天气、OD 完整性、basis 或 data version 校验失败；
- 快照内 `city_id` 与环境选择城市不一致。

生产组合根没有 `allow_candidates` 配置开关，避免通过环境变量意外放宽发布门禁。candidate 只能由审计代码显式构造 `JsonPublishedSolverDataProvider(..., allow_candidates=True)` 离线读取。

数据库迁移仍应在启动应用前通过 Alembic 独立执行；生产式启动脚本不会隐式修改数据库结构。日志继续写入模块级、按级别每日文件，不把 Key 或完整请求参数写到控制台。

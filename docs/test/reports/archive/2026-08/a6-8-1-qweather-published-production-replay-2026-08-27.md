# A6-8.1 和风真实天气、正式 Published Snapshot 与生产回放报告

- 日期：2026-08-27
- 阶段：A6-8.1 生产数据发布收口
- 城市：杭州
- 结论：真实天气、正式不可变求解数据、生产组合根和 Chrome P00→P04 回放均通过；A6-8.1 后续转入配额与快照持续服务治理

## 1. 凭证与请求安全

- 项目根目录 `.env` 已存在 `TRAVEL_AGENT_QWEATHER_API_KEY`、专属 `TRAVEL_AGENT_QWEATHER_BASE_URL`、Location ID、超时和数据版本；
- 脱敏加载确认 API Key 非空且不会进入 `QWeatherSettings.repr`；
- API Host 是无路径、无 query、无 fragment、无用户名密码的 HTTPS Host；
- API Key 仅通过 `X-QW-Api-Key` 请求头发送，URL 查询参数只包含 `location=101210101`；
- 本报告、测试输出、天气快照和正式 bundle 均未记录真实 API Key 或专属 Host。

## 2. 真实三日天气快照

生成文件：

```text
var/audit/qweather-hangzhou-2026-08-27-v1.json
```

验证结果：

```text
schema_version = weather-snapshot-envelope-v1
provider = qweather
city_id = hangzhou
location_id = 101210101
basis = forecast
data_version = qweather-hangzhou-2026-08-27-v1
dates = 2026-08-27 / 2026-08-28 / 2026-08-29
days = 3，唯一、升序、连续
content_hash = valid
credential_and_host_absent = true
legacy_query_key_absent = true
```

真实返回的日间/夜间组合天气为：

- 2026-08-27：晴转小雨，`advisory`；
- 2026-08-28：中雨转多云，`advisory`；
- 2026-08-29：小雨转晴，`advisory`。

三天均非 `extreme`，因此不触发 C5 室外景点硬排除；天气仍作为真实预报与体验提示进入结果。

## 3. 正式不可变 Published Solver Snapshot

合并输入：

```text
tests/data/hangzhou_attractions_snapshot.json
var/published/hangzhou-attractions-reviewed-2026-08-27-v1.json
var/published/gaode-hangzhou-reviewed-2026-08-27-v1.json
var/audit/qweather-hangzhou-2026-08-27-v1.json
```

生成文件：

```text
var/published/hangzhou-published-2026-08-27-v1.json
```

严格加载结果：

```text
schema_version = published-solver-data-v1
status = published
version = hangzhou-published-2026-08-27-v1
content_hash = valid
attractions = 7
coordinates = 7/7 present, human_verified
weather = 3 days, qweather forecast
od_basis = gaode
directed_od = 42/42
fallback = 0
missing = 0
```

生产 `.env` 的本地快照选择器已切换到该版本；`.env` 由 Git 忽略，不进入提交。

## 4. 生产组合根与 FastAPI 回放

使用 `ProductionHttpSettings`、`JsonPublishedSolverDataProvider` 和正式数据库组合根完成匿名用户端到端回放：

```text
readiness = ready
database = true
identity = true
review_ready = true
generation_status = completed
completion_kind = complete_success
result_schema = trip-result-v2
selected = 7
scheduled = 7
unplaced = 0
attraction_conservation = true
revision_persisted = true
```

三天结果均使用真实 forecast；午餐与晚餐均为完整留白；跨景点连接的 `travel_basis` 均为 `gaode`。验证过程中生成的 Revision 均作为历史事实保留，未覆盖、迁移或原地重算。

## 5. Chrome P00→P04 正式数据回放

Chrome 扩展、本机通信清单和 Default Profile 均检查正常。以实际 H5 production build 和生产 API 组合完成：

```text
P00 首页
→ P01 2026-08-27 至 2026-08-29，09:00 开始，21:00 结束
→ P02 选择 7 个正式景点
→ P03 确认摘要并生成
→ P04 查看三日正式结果、刷新恢复
```

交互验证：

- P01/P02/P03 均提供返回首页或“上一步”；
- 未选景点时“确认选择”真实禁用，选择 7 个后真实启用；
- 生成前条件满足时“生成我的行程”真实启用；
- P04 存在且启用“＋ 规划新行程”；
- 行程卡片用约数时间和时长区间表达，不向用户展示分钟级刚性游览承诺；
- 交通卡片展示真实交通方式、距离和耗时区间；
- 午餐、晚餐留白均显示。

实际三日节点：

```text
08-27：浙江省博物馆 → 飞来峰（驾车/打车，约 4.5km）→ 灵隐寺（步行，约 300m）
08-28：河坊街 → 雷峰塔（公交/地铁，约 3.7km）
08-29：西湖湖滨约 13:30 到达、约 2.5 小时 → 晚餐约 17:50–19:20 → 19:30 湖滨晚间表演
```

刷新后完整三日节点顺序不变，证明读取的是已持久化 Revision，而非刷新时重新随机求解。Chrome 控制台为 `0 warn / 0 error`。

## 6. 回归基线与剩余项

本轮验证：

```text
后端全量 pytest：通过（264 项基线）
前端 TypeScript：通过
H5 production build：通过
Chrome P00→P04：通过
git diff --check：通过
```

既有非阻塞项：

- H5 入口约 304 KiB，超过 244 KiB 建议阈值；
- 全仓 Ruff 仍有 46 个历史问题；
- 全项目 strict mypy 最近完整基线仍有 154 条/27 个历史文件。

仍未完成：

- 和风/高德配额看板、限流、熔断与明确降级告警；
- 跨机器缓存和旧快照继续服务策略的生产实现与演练；
- 三日之外的正式气候基线 Provider；
- A6-8.2 真实 MySQL 部署与服务恢复演练；
- 餐厅节点加入后的真实 OD 重排和新 Revision 流程；
- Gate 7 专家/用户验证。

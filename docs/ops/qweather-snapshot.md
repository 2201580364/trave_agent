# 和风三日天气快照构建与发布

- 阶段：A6-8.1
- 依据：ADR-0003、ADR-0004、ADR-0014
- 边界：和风只在发布前构建快照时联网，求解器和生产请求只读取不可变快照

## 1. 本地配置

真实凭证只写入 Git 已忽略的 `.env` 或部署 Secret：

```dotenv
TRAVEL_AGENT_QWEATHER_API_KEY=<和风项目凭证>
TRAVEL_AGENT_QWEATHER_LOCATION_ID=101210101
TRAVEL_AGENT_QWEATHER_TIMEOUT_SECONDS=5
TRAVEL_AGENT_QWEATHER_DATA_VERSION=qweather-hangzhou-YYYY-MM-DD-vN
TRAVEL_AGENT_QWEATHER_BASE_URL=<和风控制台分配的 HTTPS API Host>
```

`101210101` 是杭州 Location ID。API Host 应以和风控制台当前项目展示值为准；不要把私有 Host、Key 或含 Key 的完整请求 URL写入文档、日志、测试报告或 Git。

当前 API KEY 按和风官方方式只通过请求头发送：

```http
X-QW-Api-Key: <项目 API KEY>
```

请求查询参数只包含 `location`，禁止使用旧式 `?key=`，也禁止将凭证拼入 API Host。未配置专属 `TRAVEL_AGENT_QWEATHER_BASE_URL` 时构建命令必须失败，不再回退到逐步停用的公共 `devapi.qweather.com`。

提交前检查：

```powershell
git check-ignore -v .env
git status --short
```

## 2. 构建真实三日预报

```powershell
py -3.12 scripts/build_qweather_snapshot.py `
  --output var/audit/qweather-hangzhou-YYYY-MM-DD-v1.json `
  --data-version qweather-hangzhou-YYYY-MM-DD-v1 `
  --city-id hangzhou `
  --execute-live
```

缺少 `--execute-live` 时命令必须拒绝运行。输出 envelope 包含天气内容哈希，但不包含 API Key。

## 3. 输出检查

正式候选天气必须满足：

```text
schema_version = weather-snapshot-envelope-v1
snapshot.schema_version = weather-snapshot-v1
snapshot.provider = qweather
snapshot.city_id = hangzhou
snapshot.basis = forecast
snapshot.days = 3 个唯一连续日期
```

每个日期必须具有：

```text
date / basis / severity / condition / condition_code / source_ref / fetched_at
```

`fetched_at` 必须带时区。三日之外的日期不得补造晴天；当前没有正式气候基线时，不生成覆盖该日期的 published bundle。

## 4. 合并正式求解数据

只有路线坐标已经由发布责任人确认并写为 `human_verified` 后，才能执行：

```powershell
py -3.12 scripts/build_published_solver_snapshot.py `
  --attractions tests/data/hangzhou_attractions_snapshot.json `
  --coordinates var/published/hangzhou-attractions-reviewed-YYYY-MM-DD-v1.json `
  --od var/published/gaode-hangzhou-reviewed-YYYY-MM-DD-v1.json `
  --weather var/audit/qweather-hangzhou-YYYY-MM-DD-v1.json `
  --output var/published/hangzhou-published-YYYY-MM-DD-v1.json `
  --version hangzhou-published-YYYY-MM-DD-v1 `
  --city-id hangzhou
```

正式合并器拒绝：

- 未 `human_verified` 的坐标；
- incomplete、fallback、非 Gaode 或混合版本 OD；
- 天气 envelope 哈希篡改；
- 非和风 Provider、城市不一致、非三日 forecast；
- 缺少天气来源字段；
- 覆盖已经存在的正式快照文件。

## 5. 2026-08-27 杭州正式发布证据

- 已使用项目根目录 `.env` 中的本地 Secret 完成真实和风请求；配置检查和测试输出均未回显 API Key 或专属 Host；
- 已生成不可变天气审计快照 `var/audit/qweather-hangzhou-2026-08-27-v1.json`：三个唯一连续日期为 2026-08-27 至 2026-08-29，Provider、来源字段和内容哈希均通过；
- 7 个路线点均为 `human_verified`，审核后严格高德有向 OD 为 42/42、0 fallback、0 missing；
- 已生成并严格加载 `var/published/hangzhou-published-2026-08-27-v1.json`，状态为 `published`；
- 正式生产组合根、FastAPI 端到端生成、数据库 Revision 持久化和 Chrome P00→P04 回放均通过；详细证据见 `docs/test/reports/a6-8-1-qweather-published-production-replay-2026-08-27.md`。

## 6. 当前未完成

- 三日之外的正式月度气候基线 Provider 尚未实现；
- 和风与高德快照脚本已共用 Provider 治理接口；未配置 Redis 时使用 `var/ops/provider-governance.json`，配置 `TRAVEL_AGENT_PROVIDER_REDIS_URL` 时使用 Redis 跨机器共享状态；两种后端均实现按日安全预算、请求间隔、成功/失败分类、连续失败熔断和限流立即熔断；
- 生产组合根已支持显式已知良好旧 Published Snapshot 回退，配置与门禁见 ADR-0016；当前仍缺跨机器共享治理后端、正式配额来源/集中看板和多实例故障演练；
- A6-8.2 真实 MySQL 部署与恢复演练尚未完成。

## 7. 配额、限流与熔断配置

本地 `.env` 或部署 Secret/环境变量可配置：

```dotenv
TRAVEL_AGENT_QWEATHER_DAILY_REQUEST_BUDGET=100
TRAVEL_AGENT_PROVIDER_CIRCUIT_FAILURE_THRESHOLD=3
TRAVEL_AGENT_PROVIDER_CIRCUIT_OPEN_SECONDS=300
TRAVEL_AGENT_PROVIDER_REDIS_URL=
TRAVEL_AGENT_PROVIDER_REDIS_PREFIX=travel-agent
```

每日预算是项目侧的安全上限，不声称等于和风控制台套餐配额；生产值必须小于或等于实际可用配额并保留发布余量。状态文件不保存 API Key、专属 Host 或请求头。需要机器读取时执行：

```powershell
py -3.12 scripts/show_provider_governance.py --json
```

Redis URL 留空时使用本地 JSON。多机器发布节点必须连接同一授权 Redis；配置后连接/认证失败会终止快照构建，不会静默退回各自本地状态。正式环境还需完成 TLS、ACL、监控和断连恢复演练。

环境边界：不得在开发本机安装、启动或部署测试 Redis/MySQL 服务。真实 Redis 认证、TLS、ACL 和故障演练只在用户提供并授权的服务器上执行。

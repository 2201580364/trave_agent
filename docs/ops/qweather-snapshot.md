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

## 5. 当前未完成

- 本机 `.env` 尚未配置和风 API Key，因此当前只有离线契约与错误路径验证，没有真实和风响应证据；
- 三日之外的正式月度气候基线 Provider 尚未实现；
- 路线点已有 Chrome/高德页面复核报告，但仍等待发布责任人确认，尚未写成 `human_verified`；
- 正式杭州 published bundle 和生产 FastAPI/Chrome 回放仍未完成。

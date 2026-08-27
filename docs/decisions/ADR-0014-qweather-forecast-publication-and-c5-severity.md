# ADR-0014：和风三日预报发布门禁与 C5 天气等级映射

- 状态：Accepted
- 日期：2026-08-27
- 产品里程碑：M1
- 实现优先级：P0
- 关联：ADR-0003、ADR-0004、ADR-0005、ADR-0009、ADR-0013、H3、C5

## 背景

ADR-0003 已决定将三日内可信预报与远期气候基线分层，ADR-0004 将“极端天气排除室外景点”保留为 C5 硬约束。但 A6-8.1 生产数据收口前仍缺少以下可执行边界：

1. 和风响应如何映射为 `normal`、`advisory`、`extreme`；
2. 什么来源的天气可以驱动 C5 硬排除；
3. 正式发布天气必须保存哪些来源字段；
4. 和风三日预报之外的日期如何处理；
5. 审计用晴天 fixture 如何避免误入生产。

如果这些边界不固定，构建脚本可能把普通降雨错误升级为硬排除，也可能把缺少预报的远期日期静默伪装成晴天。

## 决策

### D1 只有真实 forecast 的 extreme 可以驱动 C5

求解器继续使用既有规则：

```text
basis=forecast AND severity=extreme AND attraction.is_indoor=false
→ C5 硬排除
```

以下情况不得触发 C5 硬排除：

- `basis=forecast, severity=advisory`：只做天气与装备提示；
- `basis=climate`：即使历史气候风险较高，也只做远期参考；
- 缺少真实天气来源：发布构建失败，不补造 `normal`；
- `audit_normal_fixture`、`deterministic_local_fixture`：只能用于候选审计或本地开发。

### D2 和风天气文字映射

当前 `qweather-severity-v1` 采用保守、可解释的中文关键词映射：

| 等级 | 条件示例 | 求解影响 |
|---|---|---|
| `normal` | 晴、多云、阴 | 不改变可用性 |
| `advisory` | 小雨、中雨、阵雨、普通降雪、雷、雾、霾、沙尘 | 不硬排除；在结果和 UI 中提示 |
| `extreme` | 暴雨、大暴雨、特大暴雨、暴雪、大暴雪、特大暴雪、台风、龙卷风、冰雹、雷暴大风、强沙尘暴 | forecast 时排除室外景点 |

日间与夜间文字不一致时合并为“日间转夜间”，以两者中更严重的关键词为当日等级。普通雨雪不得因为体验不佳而升级为物理硬约束。

映射规则发生实质变化时必须升级天气 `data_version`，保留历史 Published Snapshot 和 TripRevision 的原始判断，不原地重算。

### D3 正式天气必须可追溯

每个正式天气日记录至少包含：

```text
date
basis = forecast | climate
severity = normal | advisory | extreme
condition
condition_code
source_ref
fetched_at
```

和风三日快照外层还保存：

```text
provider = qweather
location_id
data_version
provider_update_time
fetched_at
content_hash
```

API Key 只从本地 `.env` 或部署 Secret 注入，不进入请求日志、错误明细、快照、内容哈希输入之外的命令输出或 Git。

### D4 三日范围外不得假装晴天

`/v7/weather/3d` 构建器严格要求三个唯一、连续日期。正式行程日期不在该范围内时：

- 若存在经过发布审核的月度气候基线，使用 `basis=climate` 并明确标注“气候参考”；
- 当前尚无气候基线 Provider 时，正式发布数据不覆盖该日期，由现有缺天气门禁拒绝或提示无法生成；
- 不复制第三天预报，不循环使用三日数据，不生成默认 `normal`。

### D5 联网只发生在发布前构建

和高德 OD 相同，和风 HTTP 只在显式执行发布前脚本时调用：

```text
scripts/build_qweather_snapshot.py --execute-live
```

求解、普通 API 请求、单元测试、Golden、降级和离线回放均不访问和风网络。生产 FastAPI 从不可变 Published Snapshot 读取天气，不在用户点击“生成行程”时临时访问第三方天气服务。

### D6 正式 Published Snapshot 继续 fail-fast

`JsonPublishedSolverDataProvider` 对 `status=published` 增加天气门禁：

- 天气列表不能为空且日期唯一；
- `basis`、`severity` 必须是已知枚举；
- `condition`、`condition_code`、`source_ref`、带时区 `fetched_at` 必须存在；
- `weather_basis` 含 `audit` 或 `fixture` 时拒绝；
- 天气 envelope 哈希不匹配时拒绝；
- 和风城市、Provider、三日数量或来源不一致时拒绝发布构建。

候选快照在显式 `allow_candidates=True` 时继续允许审计天气，保持历史离线证据可回放。

## 版本与契约影响

本决策实现 ADR-0003/ADR-0004 已定义的 C5，不改变公开请求结构、`trip-result-v2` 或硬约束集合，因此当前版本组合保持：

```text
solver contract    = solver-p1-v2
result schema      = trip-result-v2
constraint version = constraints-p1-v4
parameter version  = parameters-p1-2026-08-26
```

天气数据本身使用独立 `data_version` 追溯映射与抓取批次。

## 验收

- 设置对象 `repr` 不包含 API Key；
- 联网构建缺少 `--execute-live` 时失败；
- 三日响应必须完整、唯一、连续且抓取时间带时区；
- 晴/普通雨雪/暴雨分别映射为 normal/advisory/extreme；
- 429、HTTP 错误、超时、业务错误和非法响应可分类；
- 正式 Provider 拒绝缺失天气来源字段和审计 fixture；
- candidate 离线审计兼容性保持；
- 正式合并器拒绝未审核坐标、缺边/回退 OD、天气哈希篡改和城市不一致；
- 全量离线测试、Golden、降级、接近度与数据校验继续通过。

## 何时重新评审

- M1 需要覆盖三日以外的真实出行日期并决定气候基线数据源；
- 和风免费/商业套餐、认证方式或 API Host 发生变化；
- 真实用户反馈表明 advisory/extreme 映射过松或过严；
- 引入逐小时天气、景区微气候、积水、雷电或高温等更细粒度安全模型；
- 多城市发布需要按城市维护不同的灾害等级与季节风险。

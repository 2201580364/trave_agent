# M1 HTTP API 契约

- 文档版本：V2.0
- 日期：2026-08-24
- 阶段：A5 API 与持久化模型同步
- 状态：已设计，待 A6 实现
- 上游：功能模块 V3.0、UI V1.1、交互 V1.1、应用代码架构 V1.0、ADR-0005、ADR-0009
- API 前缀：`/api/v1`

## 1. 契约目标

本契约支撑 M1 首个浏览器可操作纵向切片：

```text
匿名会话
→ 创建/恢复草稿
→ 编辑旅行事实与景点选择
→ 获取生成前摘要
→ 提交 GenerationIntent
→ 查询状态
→ 查看不可变 TripRevision
→ 刷新后恢复相同结果
```

本版替代旧“`POST /trips/generate` + `/trips/{task_id}/status` + 单表 itinerary”设计。稳定重试、修改后重新生成和未来“换一个方案”使用不同语义，不再共用 `regenerate`。

## 2. 通用约定

### 2.1 协议

- JSON over HTTPS；
- UTF-8；
- 日期为 `YYYY-MM-DD`；
- 时间点为带时区 ISO 8601；M1 目的地业务时区为 `Asia/Shanghai`；
- 行程内钟点同时返回 `local_time=HH:mm` 和必要的 `day_offset`；
- 分钟字段使用整数，字段名以 `_min` 结尾；
- ID 对客户端是不透明字符串；实现可用 UUID/ULID，客户端不得解析；
- 所有响应返回 `X-Request-ID`；客户端可传合法 `X-Request-ID`，服务端也必须校验或生成。

### 2.2 身份

首切片使用匿名会话：

```http
Authorization: Bearer <anonymous_access_token>
```

- token 原值只在创建会话时返回一次；
- 服务端只保存不可逆摘要；
- token 不得出现在 URL、日志、分享内容或错误详情；
- Trip、Draft、Intent、Revision 均校验所属主体；
- 后续微信登录绑定不能改变现有资源 ID。

### 2.3 写请求并发与幂等

| 场景 | 机制 |
|---|---|
| 草稿更新 | 请求携带 `expected_draft_version`，服务端乐观锁 |
| 提交生成 | 客户端生成 `generation_intent_id`，同时固定输入 snapshot hash |
| 稳定重试 | 沿用原 `generation_intent_id`、输入快照、数据版本和 seed |
| 用户修改后生成 | 新 draft version + 新 `generation_intent_id` |
| 未来换方案 | 新的 alternative 资源/意图；M1 不提供 |

生成意图以请求体中的 `generation_intent_id` 为业务唯一键；可选 `Idempotency-Key` 请求头不能替代该字段。

### 2.4 通用错误结构

```json
{
  "error": {
    "code": "draft_version_conflict",
    "message": "草稿已在其他页面更新，请恢复最新版本后继续。",
    "request_id": "req_01K...",
    "retryable": false,
    "field_errors": [],
    "details": {
      "expected_version": 3,
      "current_version": 4
    }
  }
}
```

- `code` 是稳定机器码；
- `message` 是版本化用户文案，不作为程序判断依据；
- `retryable` 表示是否可在不改变业务输入的情况下重试；
- `details` 只保存白名单结构化信息；
- 不返回异常堆栈、SQL、文件路径、token 或 Provider 密钥。

## 3. 枚举

### 3.1 交通类型

```text
flight
high_speed_rail
train
self_drive
long_distance_bus
already_in_destination
other
```

### 3.2 必填事实确认状态

```text
unresolved
suggested
confirmed
confirmed_by_inheritance
overridden
```

生成只接受 `confirmed`、`confirmed_by_inheritance`、`overridden`。到达方式不能使用继承状态；离开方式允许从已确认到达方式继承。

### 3.3 旅行节奏和同行人群

API 旅行节奏使用求解器兼容值：

```text
speed | normal | leisure
```

UI 显示“紧凑/适中/悠闲”。同行人群：

```text
unspecified | solo | couple | friends | family_with_children | with_elderly
```

M1 同行人群只用于展示、分析和未来演进，不伪装成求解硬约束。

### 3.4 生成状态与完成结果

```text
intent status:
queued | running | completed | failed_retryable | failed_terminal

completion_kind:
complete_success | partial_success

has_soft_degradation:
true | false
```

完成范围和软降级是两个正交维度：行程可以同时 `partial_success` 且 `has_soft_degradation=true`。

### 3.5 数据精度

```text
weather_basis: forecast | climate
od_basis: gaode | approximate
```

## 4. 端点总览

| 方法 | 路径 | 用例 | 首切片 |
|---|---|---|---:|
| POST | `/anonymous-sessions` | 创建匿名主体 | 是 |
| POST | `/trip-drafts` | 创建草稿 | 是 |
| GET | `/trip-drafts/{draft_id}` | 恢复草稿 | 是 |
| PATCH | `/trip-drafts/{draft_id}/travel-facts` | 更新日期、锚点、交通和节奏 | 是 |
| PUT | `/trip-drafts/{draft_id}/attraction-selection` | 替换当前选择集合 | 是 |
| GET | `/trip-drafts/{draft_id}/review` | 获取生成前摘要和缺失项 | 是 |
| GET | `/attractions` | 景点列表、搜索和筛选 | 是 |
| GET | `/attractions/{attraction_id}` | 景点基础详情 | 是 |
| POST | `/generation-intents` | 提交生成意图 | 是 |
| GET | `/generation-intents/{intent_id}` | 查询生成状态 | 是 |
| POST | `/generation-intents/{intent_id}/retry` | 稳定重试暂时失败的同一意图 | P1 |
| GET | `/trips/{trip_id}` | 获取 Trip 摘要及当前 revision | 是 |
| GET | `/trips/{trip_id}/revisions/{revision_id}` | 获取不可变行程结果 | 是 |
| GET | `/trips` | 当前主体行程历史 | P1 |
| POST | `/trips/{trip_id}/feedback` | 整体反馈 | P1 |
| POST | `/trips/{trip_id}/revisions/{revision_id}/nodes/{node_id}/feedback` | 节点反馈 | P1 |
| POST | `/trips/{trip_id}/plan-shares` | 创建计划分享 | P1 |

M1 不提供 `/regenerate`。用户修改条件时更新或创建草稿，再提交新的 generation intent。

## 5. 匿名会话

### 5.1 POST `/anonymous-sessions`

请求：

```json
{"device_installation_id": "client_opaque_id"}
```

`device_installation_id` 可选，只用于同设备恢复提示和反滥用，不作为认证凭证。

响应 `201`：

```json
{
  "principal_id": "principal_01K...",
  "access_token": "returned_once_secret",
  "expires_at": "2026-09-23T10:30:00+08:00"
}
```

重复调用默认创建新会话；客户端已有有效 token 时不应重复创建。

## 6. 草稿资源

### 6.1 草稿表示

```json
{
  "draft_id": "draft_01K...",
  "draft_version": 4,
  "status": "editing",
  "city": {
    "city_id": "hangzhou",
    "name": "杭州",
    "timezone": "Asia/Shanghai"
  },
  "travel_facts": {
    "start_date": "2026-09-01",
    "end_date": "2026-09-03",
    "arrival": {
      "transport_type": "high_speed_rail",
      "confirmation": "confirmed",
      "arrives_at": "2026-09-01T14:00:00+08:00",
      "station_to_city_min": 45,
      "station_to_city_source": "system_default",
      "station_to_city_confirmation": "suggested"
    },
    "departure": {
      "transport_type": "high_speed_rail",
      "confirmation": "confirmed_by_inheritance",
      "departs_at": "2026-09-03T18:00:00+08:00",
      "station_early_min": 45,
      "station_early_source": "system_default",
      "last_visit_to_station_min": 40,
      "last_visit_to_station_source": "od_snapshot"
    },
    "travel_mode": "normal",
    "crowd_type": "unspecified"
  },
  "selected_attraction_ids": ["attr_1", "attr_2"],
  "visit_period_preferences": [],
  "last_saved_at": "2026-08-24T10:30:00+08:00"
}
```

系统推导值保留 `source` 和确认状态。推导失败时值为 `null`，review 返回阻断项，禁止静默使用 0。

### 6.2 POST `/trip-drafts`

请求：

```json
{"city_id": "hangzhou"}
```

响应 `201`：返回 `draft_version=1` 的草稿。M1 只允许已发布城市；未开放城市返回 `city_not_available`。

### 6.3 GET `/trip-drafts/{draft_id}`

返回当前主体可访问的最新草稿。资源不存在或无权访问统一返回 `404 resource_not_found`，避免泄露资源存在性。

### 6.4 PATCH `/trip-drafts/{draft_id}/travel-facts`

请求：

```json
{
  "expected_draft_version": 1,
  "start_date": "2026-09-01",
  "end_date": "2026-09-03",
  "arrival": {
    "transport_type": "high_speed_rail",
    "confirmation": "confirmed",
    "arrives_at": "2026-09-01T14:00:00+08:00",
    "station_to_city_min": 45,
    "station_to_city_confirmation": "suggested"
  },
  "departure": {
    "transport_type": "high_speed_rail",
    "confirmation": "confirmed_by_inheritance",
    "departs_at": "2026-09-03T18:00:00+08:00",
    "station_early_min": 45,
    "last_visit_to_station_min": 40
  },
  "travel_mode": "normal",
  "crowd_type": "unspecified"
}
```

响应 `200`：返回新版本草稿。

规则：

- `confirmed_by_inheritance` 的 departure transport 必须等于已确认 arrival transport；
- 用户选择“返程不同”后 departure confirmation 变为 `unresolved`，直到再次确认；
- `already_in_destination` 使用首日可开始时间语义，不套用交通节点接驳；
- 时间锚点必须处于旅行日期范围；
- 末日离开可用窗口必须晚于首日可开始边界；
- 高级时间值小于 0 返回字段错误；缺失不能变成 0。

### 6.5 PUT `/trip-drafts/{draft_id}/attraction-selection`

请求：

```json
{
  "expected_draft_version": 2,
  "attraction_ids": ["attr_1", "attr_2", "attr_5"],
  "visit_period_preferences": [
    {
      "attraction_id": "attr_5",
      "preferred_bucket": "evening",
      "acceptable_buckets": ["afternoon"]
    }
  ]
}
```

使用 PUT 表示完整替换选择集合，避免搜索分页和重复点击制造重复记录。

- 所有景点必须属于草稿城市；
- 未发布、停用或不可展示景点返回 `attraction_not_selectable`；
- preference 景点必须在选择集合中；
- M1 每个景点只有一个 preferred bucket，且与 acceptable 不重叠；
- 用户偏好只覆盖软时段，不改变开放时间。

### 6.6 GET `/trip-drafts/{draft_id}/review`

响应：

```json
{
  "draft_id": "draft_01K...",
  "draft_version": 3,
  "ready_to_generate": true,
  "blocking_issues": [],
  "warnings": [],
  "summary": {
    "city": "杭州",
    "date_range": "2026-09-01/2026-09-03",
    "day_count": 3,
    "arrival_transport": "high_speed_rail",
    "departure_transport": "high_speed_rail",
    "travel_mode": "normal",
    "crowd_type": "unspecified",
    "selected_attraction_count": 7,
    "time_reserve": {
      "station_to_city_min": 45,
      "station_early_min": 45,
      "last_visit_to_station_min": 40
    }
  }
}
```

`blocking_issues` 使用稳定机器码和字段路径。review 是只读校验，不创建 intent，不锁定数据版本。

## 7. 景点查询

### 7.1 GET `/attractions`

查询参数：

```text
city_id=hangzhou
query=西湖
categories=自然山水,博物馆
indoor=all|indoor|outdoor
energy_levels=1,2,3
cursor=<opaque>
limit=20
```

响应：

```json
{
  "items": [
    {
      "attraction_id": "attr_1",
      "name": "西湖风景名胜区",
      "category": "自然山水",
      "is_indoor": false,
      "energy_level": 2,
      "suggested_duration_min": 180,
      "availability_summary": "全天开放",
      "selectable": true,
      "data_version": "hangzhou-2026-08-24"
    }
  ],
  "next_cursor": null,
  "data_version": "hangzhou-2026-08-24"
}
```

排序在相同查询和数据版本下稳定。列表只展示当前发布版本允许展示的景点；不可求解但允许解释展示的项必须显式 `selectable=false`。

### 7.2 GET `/attractions/{attraction_id}`

返回 M1 基础事实、来源摘要和所选日期下开放信息。硬事实来自结构化数据，不由 LLM 生成。

## 8. 生成意图

### 8.1 POST `/generation-intents`

请求：

```json
{
  "generation_intent_id": "gen_01K...",
  "draft_id": "draft_01K...",
  "draft_version": 3
}
```

服务端按以下顺序处理：

1. 先按 `generation_intent_id` 查询已有记录；
2. 已存在时校验主体、draft ID/version，直接返回已有状态，不重新选择当前数据快照；
3. 不存在时校验主体、draft ID 和 version，并重新执行生成前业务校验；
4. 读取一个一致的 PublishedDataSnapshot；
5. 规范化输入并计算 `input_snapshot_hash`；
6. 在唯一约束保护下创建 intent 和不可变输入快照；
7. 提交 GenerationExecutor。

这样网络重发不会因为“重发期间城市发布了新数据版本”而改变原意图。数据库唯一键竞争失败后，应用重新读取已有 intent 并执行同样的关联校验。

响应 `202`：

```json
{
  "generation_intent_id": "gen_01K...",
  "status": "queued",
  "submitted_at": "2026-08-24T10:40:00+08:00",
  "poll_after_ms": 500
}
```

重复语义：

| 条件 | 结果 |
|---|---|
| 相同 ID + 相同主体 + 相同 draft ID/version | `200/202` 返回已有 intent，不重新装配数据或执行 |
| 相同 ID + 不同主体、draft ID 或 draft version | `409 generation_intent_conflict`；对无权主体仍不泄露资源详情 |
| draft version 已变化 | `409 draft_version_conflict` |
| 选择景点的数据版本变化且影响可用性 | `409 draft_needs_review` |

客户端不能传 seed、成本权重、硬约束开关或参数版本。

### 8.2 GET `/generation-intents/{intent_id}`

queued/running：

```json
{
  "generation_intent_id": "gen_01K...",
  "status": "running",
  "submitted_at": "2026-08-24T10:40:00+08:00",
  "started_at": "2026-08-24T10:40:00+08:00",
  "poll_after_ms": 1000
}
```

completed：

```json
{
  "generation_intent_id": "gen_01K...",
  "status": "completed",
  "completed_at": "2026-08-24T10:40:02+08:00",
  "result": {
    "trip_id": "trip_01K...",
    "revision_id": "rev_01K...",
    "revision_no": 1,
    "completion_kind": "partial_success",
    "has_soft_degradation": true
  }
}
```

failed：

```json
{
  "generation_intent_id": "gen_01K...",
  "status": "failed_terminal",
  "failure": {
    "code": "no_feasible_itinerary",
    "message": "当前日期、开放时间和到离边界下无法形成可行行程。",
    "retryable": false,
    "suggested_actions": ["adjust_dates", "adjust_anchors", "remove_attractions"]
  }
}
```

状态查询不触发重新执行。

### 8.3 POST `/generation-intents/{intent_id}/retry`

M1 P1。仅 `failed_retryable` 可调用，沿用原输入/数据快照、契约版本和 seed。不能用于修改条件或请求随机新方案。

## 9. Trip 与不可变 Revision

### 9.1 GET `/trips/{trip_id}`

```json
{
  "trip_id": "trip_01K...",
  "city": {"city_id": "hangzhou", "name": "杭州"},
  "start_date": "2026-09-01",
  "end_date": "2026-09-03",
  "current_revision": {
    "revision_id": "rev_01K...",
    "revision_no": 1,
    "completion_kind": "partial_success",
    "has_soft_degradation": true
  },
  "created_at": "2026-08-24T10:40:02+08:00",
  "updated_at": "2026-08-24T10:40:02+08:00"
}
```

### 9.2 GET `/trips/{trip_id}/revisions/{revision_id}`

响应顶层：

```json
{
  "trip_id": "trip_01K...",
  "revision_id": "rev_01K...",
  "revision_no": 1,
  "result_schema_version": "trip-result-v2",
  "completion_kind": "partial_success",
  "has_soft_degradation": true,
  "summary": {},
  "provenance": {},
  "accounting": {},
  "days": [],
  "unplaced": [],
  "data_rejected": [],
  "degradations": [],
  "created_at": "2026-08-24T10:40:02+08:00"
}
```

#### provenance

```json
{
  "solver_contract_version": "solver-p1-v2",
  "constraint_version": "constraints-p1-v2",
  "parameter_version": "parameters-p1-2026-08-25",
  "data_snapshot_version": "hangzhou-2026-08-24",
  "weather_basis": "forecast",
  "weather_version": "weather-hz-2026-08-24T08:00+08:00",
  "od_basis": "gaode",
  "od_version": "gaode-hz-2026-08-24",
  "search_summary": {
    "attempt_count": 4,
    "timed_out_day_count": 0,
    "best_so_far_day_count": 0,
    "no_solution_day_count": 0
  }
}
```

`random_seed` 和内部成本不向普通用户响应；它们保存在 SolverRun 审计中。

#### accounting

```json
{
  "input_count": 7,
  "scheduled_count": 6,
  "unplaced_count": 1,
  "data_rejected_count": 0,
  "conserved": true,
  "hard_constraint_violations": 0
}
```

#### days

```json
[
  {
    "date": "2026-09-01",
    "day_index": 1,
    "weather": {
      "condition": "light_rain",
      "severity": "advisory",
      "basis": "forecast"
    },
    "pace": {"level": "balanced", "notice": "当天节奏适中。"},
    "search_status": "completed",
    "timeline": [
      {
        "node_id": "node_01K...",
        "type": "visit",
        "segment": "daytime",
        "attraction": {"attraction_id": "attr_6", "name": "清河坊"},
        "arrival": {"local_time": "15:30", "day_offset": 0},
        "leave": {"local_time": "17:30", "day_offset": 0},
        "planned_duration_min": 120,
        "duration_notice": null,
        "transit_from_previous": {
          "travel_min": 20,
          "buffered_travel_min": 24,
          "basis": "gaode",
          "transport_mode": "transit",
          "distance_m": 8200,
          "fallback_reason": null
        },
        "visit_period": null
      },
      {
        "node_id": "meal_01K...",
        "type": "dinner",
        "status": "full",
        "start": {"local_time": "17:45", "day_offset": 0},
        "end": {"local_time": "19:15", "day_offset": 0},
        "duration_min": 90,
        "placement": "between_segments"
      }
    ]
  }
]
```

时间线顺序来自服务端结构化结果，客户端不得重排。

`trip-result-v2` 的交通方式取值为：

```text
walking | transit | driving
walking_estimate | taxi_estimate | transit_or_taxi_estimate
```

前三项表示 Provider 返回的真实模式；后三项表示近似推导。高德调用失败后允许透明降级，但此时 `basis` 必须为 `approximate`，`fallback_reason` 必须给出结构化原因（例如 `gaode_timeout`），页面必须显示估算口径。V1 历史 Revision 可以没有模式、距离和降级原因；读取端兼容 `trip-result-v1` 和 `trip-result-v2`，不得重写历史结果。

#### visit_period

```json
{
  "source": "curated",
  "source_ref": "CURATOR-HZ-1",
  "preferred_bucket": "evening",
  "acceptable_buckets": ["afternoon"],
  "actual_bucket": "afternoon",
  "outcome": "acceptable",
  "deviation_min": 90,
  "notice": "优选晚间，本次安排在可接受的下午时段。"
}
```

#### unplaced/data_rejected

```json
[
  {
    "attraction": {"attraction_id": "attr_5", "name": "某博物馆"},
    "code": "CLOSED_ON_DATE",
    "message": "该景点在可用日期闭馆。",
    "suggested_actions": ["change_dates", "replace_attraction"],
    "attempts": [
      {"date": "2026-09-01", "codes": ["CLOSED_ON_DATE"]}
    ]
  }
]
```

`data_rejected` 与 `unplaced` 分区：前者表示数据门禁未通过，后者表示数据有效但未进入最终路线。

#### degradations

```json
[
  {
    "code": "DINNER_REDUCED",
    "scope": {"date": "2026-09-02"},
    "severity": "notice",
    "message": "晚餐留白已缩短为 60 分钟。"
  }
]
```

软降级不能使用未排入或失败状态表达。

## 10. 反馈与计划分享（M1 P1）

### 10.1 整体反馈

`POST /trips/{trip_id}/feedback`

```json
{
  "revision_id": "rev_01K...",
  "feedback_intent_id": "feedback_01K...",
  "rating": "reasonable",
  "problem_types": ["route_too_long"],
  "comment": "第二天来回有点远"
}
```

### 10.2 节点反馈

`POST /trips/{trip_id}/revisions/{revision_id}/nodes/{node_id}/feedback`

```json
{
  "feedback_intent_id": "feedback_01K...",
  "rating": "dislike",
  "reason_code": "time_too_tight",
  "comment": null
}
```

节点反馈评价安排质量，不等于 M3 景点评分。

### 10.3 计划分享

`POST /trips/{trip_id}/plan-shares`

```json
{
  "plan_share_intent_id": "share_01K...",
  "revision_id": "rev_01K...",
  "template": "simple"
}
```

计划分享不能包含身份 token、完整私人交通信息或未来小记内容。

## 11. HTTP 状态码与错误码

| HTTP | 机器码 | 语义 | 可原输入重试 |
|---:|---|---|---:|
| 400 | `invalid_request` | JSON/请求语义无效 | 否 |
| 401 | `authentication_required` | token 缺失/失效 | 否 |
| 404 | `resource_not_found` | 不存在或无权访问 | 否 |
| 409 | `draft_version_conflict` | 草稿版本过期 | 否 |
| 409 | `generation_intent_conflict` | 同 intent 对应不同输入 | 否 |
| 409 | `draft_needs_review` | 发布数据变化影响选择 | 否 |
| 409 | `invalid_state_transition` | 当前状态不允许操作 | 否 |
| 422 | `field_validation_failed` | 字段/跨字段校验失败 | 否 |
| 422 | `arrival_transport_unconfirmed` | 到达交通未确认 | 否 |
| 422 | `departure_transport_unconfirmed` | 离开交通未确认 | 否 |
| 422 | `time_reserve_unresolved` | 接驳/返程无法推导且未确认 | 否 |
| 422 | `attraction_not_selectable` | 景点不可进入当前选择 | 否 |
| 422 | `data_gate_rejected` | 当前数据无法用于生成 | 否 |
| 422 | `no_feasible_itinerary` | 当前条件下无可行方案 | 否 |
| 429 | `rate_limited` | 请求过多 | 是，按 Retry-After |
| 500 | `internal_error` | 未预期错误 | 否；用户可稍后发起新请求 |
| 503 | `provider_unavailable` | 外部服务暂时失败 | 是 |
| 503 | `generation_temporarily_failed` | 执行器暂时失败 | 是，沿用 intent |

求解器拒绝码保持大写冻结词汇，例如 `CLOSED_ON_DATE`；应用错误码使用小写 snake_case，两者层级不同。

## 12. 轮询、限流和缓存

- 客户端按 `poll_after_ms` 轮询 intent；
- 页面离开后取消轮询，恢复时读取同一 intent；
- queued/running 响应使用 `Cache-Control: no-store`；
- 不对带身份的 Trip/Draft 响应使用公共缓存；
- 景点列表可按数据版本使用 ETag；
- 429 返回 `Retry-After`；
- 客户端超时不代表生成取消，恢复后继续查询状态。

## 13. 接口验收场景

### A5-API-01 双击生成

```gherkin
Given draft_version=3 且输入未变化
When 客户端用同一 generation_intent_id 连续提交两次
Then 只存在一个 GenerationIntent
And 只执行一次求解
And 两次响应指向同一状态或结果
```

### A5-API-02 同一意图不同输入

```gherkin
Given generation_intent_id 已绑定 snapshot A
When 客户端用同一 ID 提交 snapshot B
Then 返回 409 generation_intent_conflict
And 不覆盖 A
And 不创建第二次求解
```

### A5-API-03 草稿并发

```gherkin
Given 草稿当前版本为 4
When 页面使用 expected_draft_version=3 更新
Then 返回 409 draft_version_conflict
And 返回 current_version=4
And 不覆盖最新草稿
```

### A5-API-04 部分成功

```gherkin
Given 7 个输入景点中 1 个闭馆且其余满足硬约束
When 生成完成
Then intent.status=completed
And completion_kind=partial_success
And accounting.conserved=true
And unplaced 包含 CLOSED_ON_DATE
And hard_constraint_violations=0
```

### A5-API-05 软降级

```gherkin
Given 行程满足硬约束但晚餐缩短为 60 分钟
When 获取 revision
Then 结果包含结构化降级
And 不将晚餐降级放入 unplaced
And 不返回生成失败
```

### A5-API-06 刷新恢复

```gherkin
Given generation intent 已 completed
When 用户刷新并重新查询 intent 和 revision
Then 返回相同 trip_id/revision_id
And 不重新求解
And provenance 版本不变
```

### A5-API-07 数据版本变化

```gherkin
Given 用户选择景点后该景点在新发布版本中被停用
When 用户提交旧 draft_version 生成
Then 返回 409 draft_needs_review
And 明确受影响景点
And 不静默删除该景点
```

### A5-API-08 权限不泄露

```gherkin
Given 主体 A 请求主体 B 的 trip
When 服务端检查资源归属
Then 返回 404 resource_not_found
And 日志不包含访问 token
And 响应不泄露资源是否存在
```

## 14. A5 API 退出条件

- [x] 草稿、生成意图、Trip 和 Revision 资源分离；
- [x] 到达/离开交通及确认状态分离；
- [x] generation intent 幂等、稳定重试和修改后生成语义明确；
- [x] 应用状态、求解搜索状态、完成范围和软降级维度分离；
- [x] 结构化行程、未排入、数据拒绝、降级和 provenance 完整；
- [x] HTTP 错误码和求解拒绝码分层；
- [x] 匿名权限、token 和日志边界明确；
- [x] 首切片接口和 P1 接口区分；
- [x] 计划分享未与旅程回顾混用；
- [x] 关键接口具有 Given/When/Then 验收场景。

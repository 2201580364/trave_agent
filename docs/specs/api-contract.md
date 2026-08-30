# M1 用户 API 与 OM1 管理 API 契约

- 文档版本：V2.7
- 日期：2026-08-29
- 阶段：A6 首个浏览器可操作纵向切片
- 状态：P00–P08 核心 HTTP v1、“替换景点→新 Revision”、匿名主体行程历史、`plan-share-v1` 安全计划分享和 Revision/节点结构化反馈已实现；OM1 管理身份、会话、管理员创建/角色管理、只读审计查询和独立 `/api/v1/admin` 底座已实现，地点审核与发布端点仍待后续工作包实现
- 上游：功能模块 V3.5、管理端功能 V1.0、UI V1.4、交互 V1.4、应用代码架构 V1.3、ADR-0005、ADR-0009、ADR-0018、ADR-0019
- API 前缀：用户端 `/api/v1`；管理端 `/api/v1/admin`

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
| GET | `/trips` | 当前主体行程历史 | 是 |
| POST | `/trips/{trip_id}/feedback` | Revision 级整体反馈 | 是 |
| POST | `/trips/{trip_id}/revisions/{revision_id}/nodes/{node_id}/feedback` | Revision 节点安排反馈 | 是 |
| POST | `/trips/{trip_id}/plan-shares` | 创建不可变计划分享 | 是 |
| GET | `/plan-shares/{public_token}` | 无认证读取受限公开计划摘要 | 是 |
| POST | `/plan-shares/{public_token}/draft-copies` | 将公开计划复制为当前主体的新草稿 | 是 |
| GET | `/trips/{trip_id}/revisions` | 当前 Trip 的只读修订历史 | 是 |

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

### 9.1 GET `/trips`

返回当前认证主体可访问的正式 Trip，匿名主体天然等价于“当前设备会话可访问的行程”。列表只包含已成功创建 TripRevision 的行程；尚未生成、生成失败的 Draft/GenerationIntent 不伪装成正常 Trip 卡片。

查询参数：

```text
limit  1–50，默认 20
offset >= 0，默认 0
```

响应：

```json
{
  "items": [
    {
      "trip_id": "trip_01K...",
      "city_id": "hangzhou",
      "city_name": "杭州",
      "current_revision_id": "rev_02K...",
      "current_revision_number": 2,
      "completion_kind": "complete_success",
      "has_soft_degradation": false,
      "start_date": "2026-09-01",
      "end_date": "2026-09-03",
      "scheduled_count": 7,
      "unplaced_count": 0,
      "updated_at": "2026-08-28T11:05:00+08:00",
      "revision_count": 2
    }
  ],
  "limit": 20,
  "offset": 0,
  "has_more": false
}
```

排序固定为 `updated_at DESC, trip_id ASC`；相同更新时间使用 trip ID 稳定次排序。服务端先按 `principal_id` 过滤再分页，禁止客户端拉取全量后自行过滤。

### 9.2 GET `/trips/{trip_id}`

```json
{
  "trip_id": "trip_01K...",
  "city_id": "hangzhou",
  "city_name": "杭州",
  "start_date": "2026-09-01",
  "end_date": "2026-09-03",
  "current_revision_id": "rev_01K...",
  "current_revision_number": 1,
  "completion_kind": "partial_success",
  "has_soft_degradation": true,
  "scheduled_count": 6,
  "unplaced_count": 1,
  "revision_count": 1,
  "created_at": "2026-08-24T10:40:02+08:00",
  "updated_at": "2026-08-24T10:40:02+08:00"
}
```

响应不返回 `principal_id`、匿名 token 或内部 `source_draft_id`。不存在与越权访问统一返回 `404 resource_not_found`。

### 9.3 GET `/trips/{trip_id}/revisions`

返回该 Trip 的不可变修订摘要，固定按 `revision_number DESC, trip_revision_id ASC` 排序。查看历史只改变客户端当前查看指针，不得修改服务端 Trip 的 `current_revision_id`。

```json
{
  "trip_id": "trip_01K...",
  "current_revision_id": "rev_02K...",
  "items": [
    {
      "trip_revision_id": "rev_02K...",
      "revision_number": 2,
      "is_current": true,
      "completion_kind": "complete_success",
      "has_soft_degradation": false,
      "start_date": "2026-09-01",
      "end_date": "2026-09-03",
      "scheduled_count": 7,
      "unplaced_count": 0,
      "created_at": "2026-08-28T11:05:00+08:00"
    },
    {
      "trip_revision_id": "rev_01K...",
      "revision_number": 1,
      "is_current": false,
      "completion_kind": "complete_success",
      "has_soft_degradation": false,
      "start_date": "2026-09-01",
      "end_date": "2026-09-03",
      "scheduled_count": 7,
      "unplaced_count": 0,
      "created_at": "2026-08-27T10:30:00+08:00"
    }
  ]
}
```

### 9.4 GET `/trips/{trip_id}/revisions/{revision_id}`

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
    "constraint_version": "constraints-p1-v5",
    "parameter_version": "parameters-p1-2026-08-26",
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

### 9.5 POST `/trips/{trip_id}/revisions/{revision_id}/attraction-replacements`

M1 P1。用户从当前行程景点卡发起替换时，服务端复制基准 Revision 对应的输入草稿，仅替换一个景点，然后按当前已发布数据快照执行完整求解。旧 Revision 不修改；只有质量门通过后才把新 Revision 设置为 Trip 的当前版本。

请求：

```json
{
  "generation_intent_id": "intent_01K...",
  "old_attraction_id": "hz_west_lake",
  "new_attraction_id": "hz_museum"
}
```

成功返回 `202 Accepted`，主体结构与 GenerationIntent 查询一致，并补充本次替换草稿引用：

```json
{
  "generation_intent_id": "intent_01K...",
  "status": "completed",
  "trip_id": "trip_01K...",
  "trip_revision_id": "revision_01K...",
  "replacement_draft_id": "draft_01K...",
  "replacement_draft_version": 1
}
```

约束：

- `revision_id` 必须属于该 Trip，且必须仍是 `current_revision_id`；否则返回 `409 trip_revision_conflict`，防止并发修改覆盖新版本；
- 被替换景点必须存在于基准草稿，新景点不能已经被选择，且必须属于当前发布景点目录；
- 同一个 `generation_intent_id`、同一 Trip、同一基准 Revision 和同一替换动作重复提交时返回原状态，不重复创建草稿、求解或 Revision；
- 同一幂等 ID 被用于不同替换动作时返回 `409 generation_intent_conflict`；
- 完整求解失败时旧 Revision 继续作为当前版本，前端不得局部插卡片或伪造成功。

## 10. 反馈与计划分享（M1 P1）

### 10.1 整体反馈

`POST /trips/{trip_id}/feedback`

```json
{
  "revision_id": "rev_01K...",
  "feedback_intent_id": "feedback_01K...",
  "rating": "unreasonable",
  "problem_types": ["route_too_long", "pace_mismatch"],
  "comment": "第二天来回有点远"
}
```

`rating` 只接受 `reasonable | neutral | unreasonable`。`problem_types` 会去重并按稳定顺序保存，只接受：

```text
route_too_long
time_unreasonable
pace_mismatch
missing_attraction
attraction_data_error
explanation_unclear
```

`reasonable` 不能携带问题类型；`comment` 可空，去除首尾空格后最长 500 字。

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

`rating` 只接受 `like | dislike`；原因只接受 `arrangement_good | time_too_tight | travel_too_far | time_period_wrong | duration_wrong | attraction_data_error`。`like` 使用 `arrangement_good`，不能携带负面原因；`dislike` 可选择一个负面原因。节点反馈评价的是该 Revision 中的安排质量，不等于 M3 景点评分或评论区内容。

两个接口成功均返回 `201`：

```json
{
  "feedback_id": "feedback_01K...",
  "feedback_intent_id": "feedback_intent_01K...",
  "trip_id": "trip_01K...",
  "revision_id": "revision_01K...",
  "feedback_scope": "trip",
  "node_id": null,
  "rating": "unreasonable",
  "reason_codes": ["pace_mismatch", "route_too_long"],
  "comment": "第二天来回有点远",
  "created_at": "2026-08-28T16:00:00+08:00",
  "reused": false,
  "deduplicated": false
}
```

权限、幂等和去重规则：

- Trip 必须属于当前主体，Revision 必须属于该 Trip；节点必须真实存在于该 Revision 的不可变结果快照，失败统一为 `404 resource_not_found`；
- API 可评价当前主体拥有的任意历史 Revision；首版 UI 只在当前 Revision 展示控件，历史 Revision 保持只读；
- 同一 `feedback_intent_id` 与完整规范化载荷重试返回原反馈，`reused=true, deduplicated=false`；
- 同一 intent 被用于不同载荷时返回 `409 feedback_intent_conflict`；
- 同一主体对同一 Revision 的整体反馈只保留首份；对同一 Revision/node 的节点反馈也只保留首份。新 intent 再次提交相同目标时返回首份反馈，`reused=true, deduplicated=true`；
- A6-9.4 首版没有编辑、覆盖或追加反馈流程；去重响应不能解释为新内容已更新旧反馈。

### 10.3 计划分享

`POST /trips/{trip_id}/plan-shares`

```json
{
  "plan_share_intent_id": "share_01K...",
  "revision_id": "rev_01K...",
  "template": "simple"
}
```

创建接口需要原作者 Bearer token。当前 `template` 只接受 `simple`；成功返回 `201`：

```json
{
  "plan_share_id": "plan_share_01K...",
  "status": "published",
  "template": "simple",
  "revision_id": "revision_01K...",
  "share_schema_version": "plan-share-v1",
  "share_token": "ps1.plan_share_01K....signature",
  "share_path": "/pages/plan-share-view/index?token=...",
  "published_at": "2026-08-28T14:00:00+08:00",
  "reused": false,
  "content": {}
}
```

同一个 `plan_share_intent_id + principal_id + trip_id + revision_id + template` 重试时，返回同一个分享对象和同一个公开 token，并令 `reused=true`；同一 intent 改用于其他 Trip、Revision 或模板时返回 `409 plan_share_intent_conflict`。分享内容在创建时清洗、固化并保存，后续原 Trip 产生新 Revision 不改变已经发布的分享快照。

公开读取：

```http
GET /plan-shares/{public_token}
```

- 不要求登录；
- 返回 `Cache-Control: no-store`；
- 响应不回显 `share_token`，也不返回 `principal_id`、`trip_id`、`revision_id`、草稿 ID、内部 node/attraction ID、坐标或 OD 明细；
- 无效、伪造或已失效 token 统一返回 `404 resource_not_found`；
- `content.schema_version=plan-share-v1`、`content.content_kind=planned_itinerary`，只包含城市、日期范围、Revision 编号、每日景点名称、上午/下午/晚上、固定场次准确时间、粗粒度停留时长、天气参考、已安排/未排入计数和隐私提示；
- 计划分享不能包含匿名访问 token、精确私人交通锚点、票号/班次/站点、私人备注、旅行小记或未来媒体内容。

公开 token 使用独立 HMAC 密钥签发；服务端只保存 SHA-256 摘要，不保存 token 原值。生产环境必须配置至少 32 字节的 `TRAVEL_AGENT_PLAN_SHARE_TOKEN_SECRET`，缺失或过短时应用启动失败。该密钥、匿名 access token 和未来旅程回顾 token 必须物理分离。

访客复制：

```http
POST /plan-shares/{public_token}/draft-copies
Authorization: Bearer <recipient_anonymous_access_token>
```

返回标准 Draft DTO。新草稿只复制城市和景点集合；`travel_facts=null`、时段偏好为空，不复制原用户日期、到达/离开交通、节奏、同行人群或其他私人事实。访客必须在自己的三步流程中重新确认日期和交通；复制行为不能修改原 Trip、原 Revision 或分享快照。

## 11. HTTP 状态码与错误码

| HTTP | 机器码 | 语义 | 可原输入重试 |
|---:|---|---|---:|
| 400 | `invalid_request` | JSON/请求语义无效 | 否 |
| 401 | `authentication_required` | token 缺失/失效 | 否 |
| 404 | `resource_not_found` | 不存在或无权访问 | 否 |
| 409 | `draft_version_conflict` | 草稿版本过期 | 否 |
| 409 | `generation_intent_conflict` | 同 intent 对应不同输入 | 否 |
| 409 | `plan_share_intent_conflict` | 同一分享 intent 被用于不同 Trip、Revision 或模板 | 否 |
| 409 | `feedback_intent_conflict` | 同一反馈 intent 被用于不同规范化载荷 | 否 |
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

### A5-API-09 行程历史与 Revision 只读回看

```gherkin
Given 主体 A 有两个 Trip 且其中一个 Trip 有 Revision 1 和 Revision 2
When 主体 A 查询行程列表和该 Trip 的修订历史
Then Trip 按 updated_at 倒序并使用 trip_id 稳定次排序
And Revision 按 revision_number 从 2 到 1 返回
And Revision 2 标记 is_current=true
When 用户读取 Revision 1
Then Revision 1 仍可读取
And Trip.current_revision_id 仍指向 Revision 2
And 主体 B 的列表不包含主体 A 的 Trip
```

### A5-API-10 计划分享脱敏、幂等与回流

```gherkin
Given 主体 A 为当前 Revision 2 创建 plan-share-v1 分享
When 同一 plan_share_intent_id 重试两次
Then 两次响应指向同一 plan_share_id 和同一 share_token
And 数据库只保存公开 token 摘要和不可变脱敏快照
When 未认证访客读取公开分享
Then 响应使用 Cache-Control no-store
And 不包含 access token、主体、Trip/Revision、交通锚点、内部节点、坐标或 OD 明细
When 主体 B 选择“以此为参考新建行程”
Then 新草稿只保留城市和景点集合
And travel_facts 为 null 且时段偏好为空
And 主体 B 不能修改主体 A 的 Trip、Revision 或分享快照
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

## 15. OM1 管理 API 设计边界

本节同时记录 R0.2-05 的已实现底座和后续实现输入。R0.2-05-01A 已实现管理身份、会话、服务端 RBAC、管理员创建/角色变更和追加式审计查询；地点编辑、审核和发布端点仍不得通过通用 CRUD 暴露任意状态写入。

### 15.1 管理身份和认证

- 管理员使用独立认证上下文；匿名/普通用户 Bearer token 不能访问管理 API；
- 管理会话至少绑定 `admin_actor_id + role_set + expires_at + session_version`；
- 角色变化或会话撤销后，旧会话不能继续写入；
- 401 表示未认证/会话失效，403 表示已认证但角色不足；
- R0.2-05-01A 采用标准库 `scrypt` 密码摘要和高熵随机 Bearer token；数据库只保存密码摘要和 token SHA-256；
- 首个管理员只允许在 `admin_actors` 为空时通过成对的 `TRAVEL_AGENT_ADMIN_BOOTSTRAP_LOGIN/PASSWORD` 环境变量引导；生产部署成功后必须从部署环境移除，不能把初始密码写入代码、镜像、文档或 Git；本地开发可以将长期测试凭证保存在已被 Git 忽略的 `.env`，启动钩子在已有管理员时保持幂等，不会覆盖数据库中的密码；
- 后续可通过独立 ADR 将认证 Provider 升级为企业 SSO，但不能自动把普通 principal 提升为管理员。

### 15.2 端点族

| 方法与路径 | 最小角色 | 语义 |
|---|---|---|
| `POST /api/v1/admin/sessions` | 未认证 | 创建管理员会话 |
| `DELETE /api/v1/admin/sessions/current` | 任意管理员 | 撤销当前会话 |
| `GET /api/v1/admin/me` | 任意管理员 | 返回当前 actor、角色和权限摘要 |
| `POST /api/v1/admin/admin-actors` | admin_security | 创建独立管理员并分配最小角色；初始密码不进入审计 |
| `GET /api/v1/admin/candidates` | editor/reviewer/publisher/viewer | 查询候选和覆盖维度 |
| `POST /api/v1/admin/candidates` | data_editor | 创建最小候选，不伪造 human_verified |
| `GET /api/v1/admin/places/{place_id}` | editor/reviewer/publisher/viewer | 查询 Place、当前 Revision 和依赖摘要 |
| `POST /api/v1/admin/places/{place_id}/revisions` | data_editor | 基于指定 Revision 创建 candidate Revision |
| `PATCH /api/v1/admin/place-revisions/{revision_id}` | data_editor | 以 expected version 编辑 candidate |
| `POST /api/v1/admin/place-revisions/{revision_id}/review-tasks` | data_editor | 创建/重提审核任务；需 operation intent 和 reason code |
| `GET /api/v1/admin/review-tasks` | data_reviewer | 查询待审核队列 |
| `POST /api/v1/admin/review-tasks/{task_id}/decisions` | data_reviewer | approve、request_changes 或 cancel；写 ReviewDecision 并使用 expected version |
| `GET /api/v1/admin/review-tasks/{task_id}/decisions` | data_reviewer | 查询追加式决定历史 |
| `GET /api/v1/admin/place-revisions/{revision_id}/evidence` | editor/reviewer/publisher/viewer | 查询 Revision 绑定的几何、访问点、时间规则、闭馆日、日期例外、来源摘要和 Projection 端点；只读，不跨 Revision 推断 |
| `GET /api/v1/admin/place-revisions/{revision_id}/publication-checks` | data_publisher | 只读运行完整发布门并返回稳定拒绝码 |
| `POST /api/v1/admin/place-revisions/{revision_id}/publications` | data_publisher | 通过 publication intent 调用发布用例 |
| `POST /api/v1/admin/publication-batches` | data_publisher | 创建批次预览/执行，不隐藏逐项失败 |
| `GET /api/v1/admin/research-snapshots` | publisher/viewer | 查询不可变研究快照和质量报告 |
| `POST /api/v1/admin/research-snapshots` | data_publisher | 从明确 published 集合创建快照 |
| `POST /api/v1/admin/places/{place_id}/retirements` | data_publisher | 退役当前发布版本，不物理删除历史 |
| `GET /api/v1/admin/audit-events` | admin_security/受权只读角色 | 只读查询结构化管理审计 |
| `GET /api/v1/admin/admin-actors` | admin_security | 查询管理员和角色 |
| `PUT /api/v1/admin/admin-actors/{actor_id}/roles` | admin_security | 以 expected version 修改角色并审计 |

当前已实现端点为 sessions、current session、me、admin-actors 的创建/列表/角色变更、audit-events 只读查询，以及 R0.2-05-02 的 candidates、place-revisions、Revision evidence、review-tasks/decisions 审核闭环；地点 Revision 创建、candidate 编辑、O04 几何/访问点与 O05 时间证据写入/逐项审核、发布门检查和 Projection 级发布入口已可调用。O05 指定日期解析预览、O06 来源、O07 关系子资源和独立 research snapshot/批次发布仍属于后续切片。

`GET /api/v1/admin/candidates` 支持服务端分页参数 `limit`（1–100，默认 50）和 `offset`（非负，默认 0），按 `created_at DESC, place_revision_id ASC` 稳定排序。响应包含 `items`、请求回显的 `limit`/`offset` 和匹配筛选条件的 `total` 总数；当 `offset` 超过总数时返回空 `items`，仍保留准确的 `total`，供管理端分页控件计算页码。

几何、访问点、时间规则、来源冲突和地点关系可以作为 Revision 子资源实现，但必须保持 Revision 边界和乐观锁，不能出现绕过 Revision 的无版本 PATCH。

`GET /api/v1/admin/place-revisions/{revision_id}/evidence` 的 `sources` 只包含属于当前
Place 的来源记录；几何、访问点、时间规则、闭馆日和日期例外引用的来源也会纳入结果。`missing_source_record_ids`
显式列出缺失、错绑或不可读取的来源 ID，不能把不完整证据伪装成完整证据。来源 URL
在响应前会移除用户信息、片段并对 credential-like 查询参数脱敏；`source_url_redacted`
标记是否发生脱敏。`projection` 只返回当前 Revision 且 Place 归属一致的最新 Projection，
同一创建时间按 `projection_id` 做稳定排序；没有 Projection 时返回 `null`。`geometries[]`、
`access_points[]`、`time_rules[]`、`closures[]` 和 `date_exceptions[]` 的
`source_record_valid` 逐行标识其来源是否为当前 Place 的 active 来源记录；错绑或缺失
来源必须显示为 `false`，不能只依赖顶部汇总警告。时间分钟值允许 `0–2880`；大于等于
1440 表示跨午夜后的次日时间，客户端必须明确显示“次日”，不能对 1440 取模后隐藏日期偏移。

O04 几何与访问点写入（仅 candidate Revision）使用以下 Revision-scoped 端点：

| 方法与路径 | 最小角色 | 语义 |
|---|---|---|
| `POST /api/v1/admin/place-revisions/{revision_id}/geometries` | data_editor | 新增 candidate Geometry |
| `PATCH /api/v1/admin/place-revisions/{revision_id}/geometries/{geometry_id}` | data_editor | 编辑 Geometry 并回到 candidate review status |
| `DELETE /api/v1/admin/place-revisions/{revision_id}/geometries/{geometry_id}` | data_editor | 软停用 Geometry，不物理删除 |
| `POST /api/v1/admin/place-revisions/{revision_id}/access-points` | data_editor | 新增 candidate AccessPoint |
| `PATCH /api/v1/admin/place-revisions/{revision_id}/access-points/{access_point_id}` | data_editor | 编辑 AccessPoint 并回到 candidate review status |
| `DELETE /api/v1/admin/place-revisions/{revision_id}/access-points/{access_point_id}` | data_editor | 软停用 AccessPoint，不物理删除 |
| `POST /api/v1/admin/place-revisions/{revision_id}/evidence/{evidence_kind}/{evidence_id}/review` | data_reviewer | 对 active Geometry/AccessPoint 逐项通过或驳回 |

所有写入请求必须携带 `expected_revision_version`、`operation_intent_id`、稳定大写
`reason_code` 和可选非敏感 `reason_text`。服务端在同一事务中校验 Revision 仍为
`candidate`，原子递增 `revision_version`，重置 `solver_eligible=false`、
`conflicts_resolved=false`、`reviewed_at=null`，并追加管理审计；版本不匹配返回
`409 place_revision_version_conflict`。重复 intent 可安全重放，不同载荷返回
`409 admin_operation_intent_conflict`。Geometry/AccessPoint 变更不会自动进入
`human_verified`，必须重新送审并由 reviewer 决定；published Revision 始终只读。

逐项审核请求使用 `review_status=human_verified|rejected`，并携带
`operation_intent_id`、`reason_code` 和可选 `reason_text`。只有
`place:review:decide` 权限可以执行，且只允许处理 candidate Revision 下仍 active
的 Geometry/AccessPoint，并要求该 Revision 已存在开放的 review task。通过时写入
`reviewed_at`，驳回时清空该时间；审核操作不替代 Revision 级 review task。Revision
级 approve 会检查全部 active Geometry/AccessPoint 均为 `human_verified`，否则以
`review_revision_not_approvable` 拒绝，不能跳过逐项核验直接进入 `human_verified`。

O05 时间证据写入同样仅允许 candidate Revision：`POST/PATCH/DELETE` 分别作用于
`/time-rules/{time_rule_id}`、`/closures/{closure_id}` 和
`/date-exceptions/{date_exception_id}` 三类 Revision 子资源；创建、编辑、重新启用或
软停用均携带 `expected_revision_version`、`operation_intent_id` 和审计理由，原子递增
Revision 版本并清除求解/审核资格。逐项审核端点的 `evidence_kind` 现在支持
`time_rule`、`closure`、`date_exception`；同 intent 重放返回当前 Revision，不同载荷返回

`409 admin_operation_intent_conflict`。Revision 级 approve 同时检查所有 active 的
Geometry、AccessPoint、TimeRule、Closure 和 DateException 均为 `human_verified`。

### O05 指定日期解析预览

`GET /api/v1/admin/place-revisions/{revision_id}/time-preview?service_date=YYYY-MM-DD`
需要 `place:candidate:read`。接口只读且可重复，不改变 Revision、证据、审核或审计状态。
解析仅使用 active 且 `human_verified` 的时间证据；日期例外优先于周规则，例外关闭优先返回
关闭结果，日期例外可以覆盖周闭馆。响应包含 `open`、`windows`、`fixed_sessions`、
`applied_exception_ids`、`rule_ids` 和稳定排序的 `reason_codes`。分钟值大于等于 1440
表示次日，并返回 `CROSS_MIDNIGHT_WINDOW`；多个固定场次返回 `FIXED_SESSION_AMBIGUOUS`。

### O06 来源冲突只读面

`GET /api/v1/admin/place-revisions/{revision_id}/source-conflicts` 需要
`place:candidate:read`，按 `source_id` 聚合当前 Revision 依赖闭包中的来源记录；
当同一来源存在不同内容指纹时返回冲突记录及 `resolved` 状态。该接口只读，来源裁决
仍须通过后续 O06 写入工作流完成，不能由前端自行推断或修改 `conflicts_resolved`。

`POST /api/v1/admin/place-revisions/{revision_id}/source-conflicts/resolve` 需要
`place:candidate:write`，请求携带 `expected_revision_number`、`expected_revision_version`、
`resolved`、`operation_intent_id` 和审计理由。服务端仅允许 candidate Revision，成功后原子
递增 Revision 版本并记录 `PLACE_SOURCE_CONFLICTS_RESOLVED` 审计；重复 intent 可重放，版本
冲突和非 candidate 均拒绝。该动作不会直接修改来源记录，Revision 仍须重新送审。

### 15.3 管理写入通用字段

```json
{
  "operation_intent_id": "uuid",
  "expected_version": 3,
  "reason_code": "SOURCE_CONFLICT_RESOLVED",
  "reason_text": "可选、非敏感、长度受限"
}
```

- `operation_intent_id` 保证双击和网络重发稳定；同 ID 不同规范化载荷返回 409；
- `expected_version` 防止编辑、审核和角色变更静默覆盖；
- 发布必须使用独立 `publication_intent_id`，不能复用编辑或审核 intent；
- reason text 不允许 API Key、密码、token、Cookie、个人联系方式、第三方页面全文或 Gate 7 原始研究内容。

### 15.4 管理错误码

| HTTP | 机器码 | 语义 |
|---:|---|---|
| 401 | `admin_authentication_required` | 管理会话缺失、失效或已撤销 |
| 403 | `admin_permission_denied` | 当前角色不能执行操作 |
| 409 | `admin_operation_intent_conflict` | 同 intent 对应不同载荷 |
| 409 | `admin_login_name_conflict` | 管理员登录名已存在 |
| 409 | `admin_actor_version_conflict` | 管理员角色 expected version 已过期 |
| 409 | `admin_role_safety_violation` | 试图移除最后一个有效 admin_security 等安全门失败 |
| 409 | `place_revision_version_conflict` | expected version 已过期 |
| 409 | `review_task_conflict` | 审核任务状态或 expected version 不允许该决定 |
| 409 | `review_revision_not_candidate` | 只有 candidate Revision 可以送审 |
| 409 | `review_revision_not_approvable` | Revision 当前状态不允许通过 |
| 409 | `admin_operation_intent_conflict` | operation intent 已被其他审核载荷使用 |
| 409 | `published_revision_immutable` | 试图原地修改 published Revision |
| 422 | `review_requirements_not_met` | 送审/通过所需依赖不完整 |
| 409 | `publication_gate_rejected` | 发布依赖闭包失败；详情含稳定 reason codes |
| 422 | `conditional_source_staging_only` | conditional 来源不能进入 published |
| 422 | `overlap_resolution_required` | 地点重叠或互斥尚未裁决 |

`publication_gate_rejected` 的 `details.reason_codes` 直接使用 PlaceCatalog 稳定拒绝码，不由前端将错误字符串猜成状态。

### 15.5 OM1 API 验收场景

```gherkin
Given 普通匿名用户拥有有效 access token
When 调用 /api/v1/admin/places
Then 返回 401 或 403
And 不泄露候选、管理员或审核信息

Given data_editor 已编辑 candidate Revision
When 直接请求 publications 端点
Then 服务端按角色和业务状态拒绝
And 不把 Revision 改为 human_verified/published

Given human_verified Revision 缺少已审核 departure access point
When data_publisher 运行 publication check 或 publication
Then 返回 publication_gate_rejected
And details 包含稳定缺失端点 reason code
And Revision/Projection 状态不变

Given 同一 publication_intent_id 和相同载荷被提交两次
When 第一次已经成功
Then 第二次返回同一发布结果
And 不重复创建 Projection、快照或审计终态
```

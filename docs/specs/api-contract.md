# API 契约（M1）

> 基础：RESTful，微信登录，限流。异步任务用 Celery + 轮询/WebSocket。

## 端点清单

| 方法 | 路径 | 说明 | 关联功能 |
|---|---|---|---|
| GET | `/api/attractions` | 景点列表 + 类型/室内外筛选 | #4 |
| GET | `/api/attractions/{id}` | 景点详情（含解析后的当天时间窗） | #4 |
| POST | `/api/trips/generate` | 一键生成分日行程（异步） | #5 |
| GET | `/api/trips/{task_id}/status` | 查询生成任务状态 | #5 |
| GET | `/api/trips/{id}` | 行程详情（分日安排） | #5 |
| POST | `/api/trips/{id}/regenerate` | 替换景点 + 重新生成 | #6 |
| POST | `/api/trips/{id}/feedback` | 👍👎 反馈 | #8 |
| POST | `/api/trips/{id}/share-card` | 生成分享卡片（服务端渲染） | #7 |

## 核心契约：生成行程

### POST /api/trips/generate

```json
{
  "city_id": 1,
  "attraction_ids": [1,2,3,5,9],
  "travel_mode": "normal",          // speed | normal | leisure
  "crowd_type": "solo",
  "start_date": "2026-09-01",
  "end_date": "2026-09-03",
  "arrival_time": "2026-09-01T14:00:00",
  "departure_time": "2026-09-03T16:00:00",
  "transport_type": "high_speed_rail",
  "visit_period_preferences": [
    {
      "attraction_id": 16,
      "preferred_bucket": "evening",
      "acceptable_buckets": ["afternoon"]
    }
  ]
}
```

### 响应（异步，202）

```json
{ "task_id": "a1b2c3", "status": "pending" }
```

### GET /api/trips/{task_id}/status

```json
{ "task_id": "a1b2c3", "status": "completed", "trip_id": 100 }
// status ∈ pending | running | completed | failed
```

### GET /api/trips/{id}（行程详情核心结构）

```json
{
  "id": 100,
  "weather_basis": "forecast",
  "days": [
    {
      "day": 1, "weekday": 2, "weather": "light_rain",
      "visits": [
        { "attraction_id": 6, "arrival": "15:30", "leave": "17:30",
          "reason": "清河坊顺路，体力适中" }
      ],
      "unplaced": [
        { "attraction_id": 5, "reason": "周一闭馆" }
      ],
      "indoor_alternatives": [
        { "attraction_id": 10, "reason": "备选室内景点，雨天可用" }
      ]
    }
  ]
}
```

## 关键约定

- **硬约束结果机器可证**：`unplaced` 数组必须列出「未排入景点 + 原因」，不接受静默丢弃。
- **天气标注来源**：`weather_basis` 区分 `forecast`（≤3天）与 `climate`（>3天），前端据此标注「气候参考」。
- **LLM 只生成 `reason` 文案**：`reason`（解释理由）由 LLM 生成，但 `arrival/leave/attraction_id` 等结构由求解器确定（大模型边界规则）。
- 异步任务超时：求解 >30s 触发降级兜底（ADR-0003 D3）。

## 后续受控多样性契约边界（ADR-0006，尚未在 M1 实现）

- `replay`：沿用原输入快照、版本和 seed，用于重试/恢复，结构化结果必须一致；
- `alternative`：用户显式请求新方案，使用新 seed，但仍必须满足硬约束、景点守恒、锁定项和近优阈值；
- 未来不得继续用含义模糊的 `regenerate` 同时表达系统重试、替换景点和“换一个方案”；
- 当前 M1 API 不接受客户端任意 seed，也不承诺可生成替代方案。

## 游览时段软偏好字段（ADR-0008）

请求中的 `visit_period_preferences` 是用户级覆盖项；应用层必须与人工策展、公开攻略候选按 `user > curated > public_guide_synthesis` 合并，再将单一有效偏好交给求解器。同级冲突返回结构化校验错误，不按数组顺序覆盖。

带偏好的行程项在 `visits[]` 中增加：

```json
{
  "visit_period": {
    "source": "curated",
    "source_ref": "CURATOR-HZ-1",
    "preferred_bucket": "evening",
    "acceptable_buckets": ["afternoon"],
    "actual_bucket": "afternoon",
    "outcome": "acceptable",
    "deviation_min": 90,
    "notice": "优选 evening 时段；本次安排在可接受的 afternoon 时段"
  }
}
```

无时段偏好的景点返回 `visit_period: null` 或省略该字段。`fallback` 只表示体验降级，不得映射成未排入或 C2 错误。

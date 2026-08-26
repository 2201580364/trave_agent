# M1 求解器公开契约（当前 solver-p1-v2；历史 solver-p1-v1）

- **状态**：已稳定并版本化（求解器核心阶段性完成，可按 ADR 升级）
- **日期**：2026-08-26
- **依据**：ADR-0009、ADR-0010、ADR-0011
- **关联假设**：H3、H7

## 1. 应用层调用边界

应用层负责加载和校验数据，求解器不直接访问 HTTP、数据库、Redis、地图、天气或 LLM：

```text
应用层
→ 解析用户请求和来源优先级
→ 加载已校验景点、天气和 OD
→ 构造 AttractionPreference + TripTimeAnchors
→ assign_days()
→ route_itinerary()
→ evaluate_solver_quality()
→ evaluate_itinerary_degradation()
→ presentation mapper / persistence / audit
```

## 2. 必需输入

### 行程上下文

```text
trip_dates: 递增、唯一的日期
travel_mode: speed | normal | leisure
anchors: 到达、接驳、离开、提前到站、末景返程分钟
weather_by_date: 每日 forecast 或 climate 数据
```

### 景点输入

每个景点必须有唯一 ID，并通过数据门禁。硬事实包括：

```text
close_days
open_on_dates / closed_on_dates
time_rules / last_entry
is_always_open
suggested_duration
is_indoor
energy_level
data_verified / conflict / active
```

时段软偏好附着于当前 `AttractionPreference`，不写入开放时间硬事实。

### 交通输入

`TravelTimeProvider` 返回有向 OD。不同景点之间的耗时必须大于零，并包含：

```text
basis
data_version
fetched_at
travel_mode（真实路网可用时）
distance_m（可用时）
fallback_reason（仅透明近似降级时）
```

缺失 OD 不能按零处理。高德 HTTP 调用只发生在 OD 快照构建阶段，求解阶段只读取已构建的版本化有向 OD；A→B 与 B→A 不得互相替代。

## 3. 核心输出

`ItineraryPlan` 至少包含：

```text
days
unplaced
data_rejected
reassignments
validations
valid
segmented_days
search_attempts
```

每个 `RouteVisit` 至少包含：

```text
attraction
arrival_min / leave_min
planned_duration_min
travel_from_previous
buffered_travel_from_previous_min
duration_notice
visit_period
```

`visit_period` 在无偏好时为空；存在偏好时包含来源、实际时段、结果、偏差分钟和提示。

当前 `trip-result-v2` 的节点接驳字段还包括：

```text
transport_mode
travel_basis
travel_distance_m
travel_fallback_reason
```

真实模式为 `walking/transit/driving`；近似交通使用 `walking_estimate/taxi_estimate/transit_or_taxi_estimate`。`travel_basis=gaode` 不得携带降级原因；高德失败后使用近似 OD 时，必须同时返回 `travel_basis=approximate` 和结构化 `travel_fallback_reason`。

## 4. 质量门禁

```text
input attractions
= scheduled
+ unplaced
+ data rejected
```

最终输出要求：

```text
accounting.conserved = true
hard_constraint_violations = 0
quality.gate_passed = true
```

接近度和其他软质量指标不能补偿门禁失败。

## 5. 搜索状态

| 状态 | 语义 |
|---|---|
| `empty` | 当天没有需要求解的景点 |
| `completed` | 已找到并完成正常搜索 |
| `best_so_far` | 时间上限内有可行解，但搜索未完整结束 |
| `time_limit_no_solution` | 超时且没有可行解 |
| `no_solution` | 搜索结束并确认无解 |
| `invalid` | 求解模型或输入状态无效 |

跨天恢复不得覆盖早期搜索尝试记录。

## 6. 拒绝码分类

### 数据准入

```text
DATA_UNVERIFIED
DATA_CONFLICT
INACTIVE
```

### 日期、开放和天气

```text
NO_AVAILABLE_DATE
NO_MATCHING_TIME_RULE
TIME_RULE_CONFLICT
CLOSED_ON_DATE
EXTREME_WEATHER_OUTDOOR
NO_WEATHER_SAFE_DATE
WEATHER_DATA_MISSING
EMPTY_DAY_WINDOW
DAY_CAPACITY_EXCEEDED
```

### 时间、交通和路由

```text
ARRIVAL_AFTER_LATEST_ARRIVAL
VISIT_DURATION_INSUFFICIENT
OD_DATA_MISSING
TRANSIT_INFEASIBLE
ROUTING_UNPLACED
NO_FEASIBLE_ROUTE
SOLVER_TIME_LIMIT
ANCHOR_VIOLATION
REASSIGNMENT_DISPLACES_EXISTING
```

应用层必须按码映射用户文案，不能展示 Python 异常或依赖当前英文枚举名作为最终文案。

## 7. 软降级

以下结果不是硬失败：

```text
建议时长不足但不低于硬比例
体力节奏偏紧/偏松
晚餐 90min → 60min → unscheduled
午餐 60min → unscheduled（当前为结果空档派生的过渡实现）
DAY_SPREAD 无安全余量时回退原硬可行时序
时段 preferred → acceptable → fallback
OD approximate（需如实标注）
best_so_far（需如实标注）
```

软降级必须保留结构化结果和提示。

## 8. 默认参数

默认值以机器快照为准：

```text
docs/test/reports/solver-p1-contract.json
```

代码来源：

```python
DEFAULT_SOLVER_P1_CONTRACT
```

修改任一默认参数必须升级 `parameter_version` 并重新生成报告。

当前版本：

```text
contract_version   = solver-p1-v2
constraint_version = constraints-p1-v2
parameter_version  = parameters-p1-2026-08-25
result_schema      = trip-result-v2

day spread target end = 16:00
day spread max delay  = 60min
lunch preference      = 11:30–14:00
lunch full duration   = 60min
```

`DAY_SPREAD` 只在 OR-Tools 已选硬可行顺序之后进行软精修：优先把最低可玩时长扩展至建议时长、保留午餐空档并覆盖下午；它不能改变顺序、突破硬窗口或牺牲固定晚间场次。

`solver-p1-v1` 和 `trip-result-v1` 继续作为历史回放版本保留。历史 TripRevision 不迁移、不覆盖、不原地重算；读取端兼容 V1/V2，新生成结果使用 V2。

## 9. 确定性和回放

M1 默认只生成稳定主方案。完整回放键为：

```text
input_snapshot_hash
data_snapshot_version
contract_version
constraint_version
parameter_version
random_seed
```

同一回放键要求相同结构化输出。运行耗时等观测噪声不参与结构化相等性。

## 10. 应用层不得假设

应用层不得假设：

- 所有景点都会排入；
- 搜索成功必然是完整搜索；
- OD 必然是真实数据；
- 晚餐必然能安排；
- 时段偏好必然命中；
- 没有 `unplaced` 就没有降级提示；
- 接近度通过等于用户满意；
- `regenerate` 等于生成随机替代方案。

## 11. 延期能力

M1 契约不承诺：

- 受控多样性候选；
- 客户端自定义 seed；
- 多峰优选时段；
- 自动专家评分；
- 酒店和餐厅联合优化（M2 先实现餐厅真实节点和重排）；
- 实时行中动态重排。

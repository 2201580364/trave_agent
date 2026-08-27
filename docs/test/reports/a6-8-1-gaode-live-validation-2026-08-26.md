# A6-8.1 高德真实路网联网验证报告

- 验证日期：2026-08-26
- 城市：杭州（330100）
- 快照版本：首轮 `gaode-hangzhou-2026-08-26-v1`；候选坐标严格重建 `gaode-hangzhou-coordinate-candidate-2026-08-26-v2`
- 结果契约：`solver-p1-v2 / trip-result-v2`
- 当前软目标与参数：`constraints-p1-v4 / parameters-p1-2026-08-26`（ADR-0013）
- 凭证：本地 `.env` 注入；报告、快照、日志和命令输出均不包含 Key

## 1. 结论

| 验证层 | 状态 | 结论 |
|---|---|---|
| Key、网络和高德接口可用性 | 通过 | 步行、公交/地铁、驾车真实请求均成功返回过有效路线 |
| 严格有向 OD 快照 | 通过 | 42/42 最终有向边来自高德，0 approximate，0 missing |
| Key 安全 | 通过 | `.env` 被 Git 忽略且未跟踪；快照中未发现 Key |
| V2 Gateway 消费真实 OD | 通过 | 七景点三日求解成功，所有实际日内接驳均为 `basis=gaode` |
| 配额与连续构建能力 | 技术验证通过，生产治理待完成 | 默认 1.05 秒节流下完整重建无 rate limit；已有跨进程 JSON 缓存和失败明细，配额看板/熔断仍待实现 |
| 入口坐标和旅游体验抽查 | 候选完成，人工发布待处理 | 7 点均取得可追溯高德 POI 候选；尚未逐点完成人工入口审核和官方页面/客户端核对 |
| OD 感知分天质量 | V4 修复并离线通过 | 数量由 `3/3/1` 修正为 `2/3/2`，建议时长负载改善为 `300/290/210min`，强近邻保持同日 |
| JSON 发布 Provider | 技术验证通过 | SHA-256、candidate/published、人工审核、坐标来源、完整有向 OD 和版本一致性门禁通过 |
| 生产可用性 | 未通过 | 生产 fail-fast 组合根已完成；尚无正式发布表/快照、真实天气、跨机器缓存、配额监控和入口坐标人工确认 |

因此，A6-8.1 的“真实 Provider 可用”“求解器可消费真实 OD”“候选路线点可重建完整快照”和“发布 JSON 可离线回放”均已有真实环境或离线技术证据，但不能将候选数据描述为正式生产发布。

## 2. 严格快照结果

使用三种模式：

```text
walking
transit
driving
```

严格模式未开启 approximate fallback：

```text
requested_pair_count = 42
gaode_pair_count     = 42
fallback_pair_count  = 0
missing_pair_count   = 0
```

最终稳定选择分布：

```text
driving = 30
transit = 8
walking = 4
```

范围：

```text
duration = 4–44 min
distance = 262–12,163 m
```

42 条有向边中，36 条在耗时、距离或交通模式上与反方向不同，证明 A→B/B→A 独立构建生效。

底层模式请求中发生 4 次 `no_route`，但相同 OD 的其他模式成功，因此没有造成最终缺边。首轮旧快照只保存聚合失败类别，无法事后还原这 4 次失败的具体 pair/mode；修复后的构建器已经为后续构建保存脱敏的 pair、mode、code、`infocode` 和发生时间。

## 3. 典型真实结果

```text
西湖湖滨 → 湖滨晚间表演
walking, 262m, 4min

浙江省博物馆 → 西湖湖滨
driving, 2,949m, 20min

灵隐寺 → 飞来峰
walking, 1,164m, 16min

飞来峰 → 灵隐寺
walking, 524m, 7min

灵隐寺 → 河坊街
driving, 12,163m, 36min

雷峰塔 → 灵隐寺
driving, 6,346m, 27min
```

灵隐寺/飞来峰双向步行距离差异较大，需要进一步核对实际游客入口、景区内部步行网络和高德客户端同点位结果，不能仅因 API 成功就认定入口数据已校准。

## 4. Key 与数据安全

验证结果：

```text
GAODE_KEY_CONFIGURED = true
DOTENV_TRACKED       = false
KEY_PRESENT_IN_SNAPSHOT = false
```

真实快照保存在 Git 忽略的 `var/published/`，尚未进入正式发布数据。审核通过前不得直接作为生产快照提交或发布。

## 5. 配额诊断

完整快照构建约发起 126 次底层模式请求。其后执行公交/地铁专项诊断时：

```text
gaode available = 15
no_route        = 2
rate_limited    = 25
missing         = 27
```

这表明当前 Key/账号/接口存在实际配额或限流边界。由于触发限流的旧诊断是在失败明细修复前生成，未保存高德原始 `infocode`，不能严谨判断是日配额、账号配额还是其他限制；本轮停止继续请求，避免扩大消耗。后续构建已经能够保留脱敏 `infocode`。

后续必须：

1. 在高德控制台核对 Web 服务各接口剩余额度；
2. 使用已实现的失败明细保存脱敏 `infocode`、模式、origin/destination 和发生时间；
3. 复用已实现的本机跨进程 JSON 缓存，后续再升级为跨机器共享缓存；
4. 将全量构建改为受控发布任务，而不是普通 API 请求路径；
5. 为配额不足定义延迟重试和旧快照继续服务策略。

## 6. 求解器真实 OD 消费验证

把严格快照转为 `InMemoryTravelTimeProvider` 后，经 `ProductionSolverGateway` 执行七景点三日求解：

```text
result_schema          = trip-result-v2
solver_version         = solver-p1-v2
completion             = complete_success
quality_gate           = true
day_counts             = [2, 2, 3]
scheduled              = 7
unplaced               = 0
conserved              = true
connected_nodes        = 4
gaode_connected_nodes  = 4
fallback_connected     = 0
distance_present       = true
```

实际分天：

```text
Day 1：雷峰塔 → 灵隐寺
Day 2：河坊街 → 西湖湖滨
Day 3：浙江省博物馆 → 飞来峰 → 湖滨晚间表演
```

技术上，真实高德 OD 已进入 V2 求解结果；体验上，该组合暴露了分天阶段的缺陷：`_balanced_default_preferred_dates()` 只按时长、体力、数量和日期容量均衡，不使用 OD 成本。Step 2 只能优化已经分到同一天的景点顺序，无法把灵隐寺和飞来峰重新聚到同一天。

这说明当前 `quality_gate=true` 只证明硬约束、守恒和结构化结果通过，不代表跨区域旅游动线已经合理。

## 7. 修复后离线回放

依据 ADR-0012，已完成两项确定性修复：

1. 默认分天使用已发布有向 OD 的对称成本做 average-linkage 聚类，再交由 C1/C2/C4/C5 可用性和容量逻辑决定最终日期；
2. 先求晚间段，日间 OR-Tools 排序把“日间末节点 → 晚间首节点”的真实 OD 作为终端成本；时间和 C6 仍由合并阶段计算，不重复计时。

使用原始严格快照纯离线重放，不发起高德请求：

```text
completion            = complete_success
quality_gate          = true
day_counts            = [2, 3, 2]
scheduled             = 7
unplaced              = 0
conserved             = true
connected_nodes       = 4
gaode_connected_nodes = 4
total_travel_min      = 50
total_distance_m      = 7,594
```

修复后稳定结果：

```text
Day 1：飞来峰 → 灵隐寺
Day 2：浙江省博物馆 → 西湖湖滨 → 湖滨晚间表演
Day 3：河坊街 → 雷峰塔
```

与修复前约 23,195m/109min 相比，道路距离约减少 67%，接驳时间约减少 54%。该回放证明当前七景点样本的缺陷已被修复，但仍不等同于真实专家/用户已经认可路线。

## 8. 候选坐标严格重建与 V4 回放

使用高德 POI V3 `place/text`、`place/around` 和 `assistant/inputtips` 对 7 个景点进行候选点位审计。首次连续无间隔查询中两次出现 `infocode=10021`；按约 1.2 秒节流后，所有有效请求均返回 `status=1 / infocode=10000`。候选坐标及偏移明细见 `a6-8-1-gaode-coordinate-audit-2026-08-26.md`。

使用候选点位、1.05 秒请求间隔和严格模式重新构建 42 条有向 OD，耗时约 132.8 秒：

```text
requested_pair_count = 42
gaode_pair_count     = 42
fallback_pair_count  = 0
missing_pair_count   = 0
mode_failures        = 4

driving = 23
transit = 15
walking = 4

duration = 5–61min
distance = 324–11,587m
```

4 次模式失败均为公交 `no_route / infocode=10000`，没有造成最终缺边；节流后没有再次出现 `rate_limited`。36 条有向边在耗时、距离或模式上与反向不同。

首次用候选真实 OD 求解形成 `3/3/1`，雷峰塔单独占一天。只做数量均衡后虽然成为 `3/2/2`，但每日建议游览负载约为 `420/210/170min`。ADR-0013 增加数量与建议时长两级均衡后，离线稳定结果为：

```text
Day 1：飞来峰 → 灵隐寺
Day 2：浙江省博物馆 → 西湖湖滨 → 湖滨晚间表演
Day 3：雷峰塔 → 河坊街

day_counts       = [2, 3, 2]
day_durations    = [300, 290, 210]
total_travel_min = 80
total_distance_m = 7,135
gaode            = 4/4
scheduled        = 7
unplaced         = 0
conserved        = true
```

结果哈希：

```text
98705e1a8e3a92c62eb415126015faa367efa997b589b40ce26af2c4cff2b687
```

候选数据已组合为 `published-solver-data-v1` bundle，并通过 `JsonPublishedSolverDataProvider(..., allow_candidates=True)` 完全离线回放。bundle 天气明确为 `audit_normal_fixture`，不是实时天气；坐标仍为 `gaode_matched_manual_review_pending`，因此默认 Provider 会拒绝，不能切换到 `published`。

## 9. 后续顺序

1. 人工确认浙江省博物馆入口、灵隐寺/飞来峰联游入口、西湖湖滨代表点，并抽样比对客户端路线；
2. 将审核通过的路线点标记为 `human_verified`，使用新版本重建并发布正式 OD/天气快照；
3. 将正式 PublishedDataProvider 接入生产组合根、FastAPI 和 Chrome 页面；
4. 建设配额看板、熔断、跨机器缓存和旧快照继续服务策略；
5. 完成生产接入后进入 A6-8.2 真实 MySQL 与部署恢复验证。

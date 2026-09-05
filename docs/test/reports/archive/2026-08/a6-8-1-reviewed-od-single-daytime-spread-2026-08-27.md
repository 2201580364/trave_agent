# A6-8.1 审核后真实 OD 单日间节点下午展开回归报告

- 验证日期：2026-08-27
- 关联：H3、C2、C4、C6、S1、LUNCH_BLOCK、DINNER_BLOCK、DAY_SPREAD
- 决策：ADR-0015
- 坐标版本：`hangzhou-attractions-reviewed-2026-08-27-v1.json`
- OD 版本：`gaode-hangzhou-reviewed-2026-08-27-v1`
- 审计 bundle：`hangzhou-reviewed-od-audit-2026-08-27-v1`
- 求解器版本：`solver-p1-v2 / trip-result-v2 / constraints-p1-v5 / parameters-p1-2026-08-26`

## 1. 回归背景

7 个杭州路线点完成人工审核并使用新坐标重建 42/42 严格高德有向 OD 后，离线求解把西湖湖滨和 19:30 的湖滨晚间表演分在同一天。原 `DAY_SPREAD` 只扩展单个日间景点的游览时长，不移动其到达时间，得到：

```text
西湖湖滨：09:00–11:30
午餐：11:30–12:30
晚餐：17:52–19:22
湖滨晚间表演：19:30–19:50
```

12:30–17:52 约 5 小时 22 分钟没有安排或解释。该结果硬约束通过，但不满足用户已经确认的“宽松行程应适当使用建议时长，并避免景点集中在上午、下午大段空白”要求。

## 2. 修复口径

当一天只有一个普通日间节点且存在固定晚间段时：

1. 先在窗口允许时扩展至建议游览时长；
2. 在首景点前保留 `11:30–14:00` 内至少 60 分钟午餐；
3. 以约 16:00 离开日间节点为稳定目标；
4. 保留真实跨段 buffered OD；
5. 保留固定晚间节点前完整 90 分钟晚餐；
6. 不改变固定场次，不突破开放时间、`last_entry` 或 C4 锚点；
7. 任一条件不满足时回退扩展后的原硬可行时序。

多日间节点的 60 分钟局部移动上限保持不变；单节点因没有日间内部顺序和 OD，不使用该局部上限，但仍受约 16:00 目标和全部安全边界约束。

## 3. 新审核 OD 完整离线回放

通过：

```python
JsonPublishedSolverDataProvider(..., allow_candidates=True)
ProductionSolverGateway(...)
```

对 7 个景点、3 天行程重复求解两次。结果：

```text
completion_kind             = complete_success
quality_gate_passed         = true
constraint_version          = constraints-p1-v5
scheduled_count             = 7
unplaced_count              = 0
data_rejected_count         = 0
hard_constraint_violations  = 0
accounting.conserved        = true
stable_hash                 = true
result_hash                 = 48e1d592e3ddcaf8128d81f856cf3970c4f18deec2fdbfde395dc6b2399aa5c8
```

关键日结果：

```text
午餐：11:30–12:30（full，before_first_visit）
西湖湖滨：13:30–16:00，计划停留 150min
晚餐：17:52–19:22（full，between_segments）
西湖湖滨 → 湖滨晚间表演：gaode walking，386m，6min
湖滨晚间表演：19:30–19:50
```

原来的 5 小时 22 分钟下午空白被日间景点覆盖，固定表演、真实接驳和午晚餐均未被破坏。

## 4. 反例与回退

新增 Step 3 反例将日间景点 `last_entry` 设置为 11:00。求解器保持：

```text
日间景点 arrival = 09:00
建议游览时长仍尽可能完整
固定晚间节点 arrival = 19:30
最终硬约束校验通过
```

证明精修不会为了覆盖下午突破最晚入园。

## 5. Gate 6 回归

```text
全量 pytest：258 passed
Golden Cases：8/8
Degradation：8/8
Closeness：0.975
Data validation：7/7
PERF-12-3 P95：14.94ms
PERF-20-7 P95：19.32ms
改动文件 Ruff：通过
本轮实现文件隔离 strict mypy：通过
前端 TypeScript：通过
H5 production build：通过（保留既有约 304 KiB 警告）
```

## 6. 结论

该回归已经收口，可以进入真实天气和正式 Published Snapshot 构建。它仍只是 Gate 6 技术证据，不代替 Gate 7 的专家或用户认可验证；审计 bundle 使用 `audit_normal_fixture` 天气，不能进入生产。

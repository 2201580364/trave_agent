# 测试方案

> G6 产物。测试不是实现后的阶段，而是与实现交替进行（约束 TDD）。

## 测试分层

| 层 | 内容 | 对应目标 |
|---|---|---|
| 单元测试 | 每个硬约束一条：开放时间、闭馆日、体力预算、时间窗、到达/离开锚点 | 「硬约束 100% 通过」变成机器可证 |
| Golden Case 回归 | 人工构建 3–5 条「专家行程」基准，求解器输出与基准对比 | 防止算法改动「改好局部、改坏全局」 |
| 数据校验测试 | `data_verified` 覆盖率、开放时间格式/范围一致性 | 数据质量门禁 |
| LLM eval | 结构化抽取人工抽检比例 + 解释生成样例评测 | LLM 输出质量 |
| 性能测试 | N=20/D=7 求解 < 2min、典型场景 < 30s 的自动化基准 | 性能目标 |

## Golden Case 定义（核心）

> 由领域专家手工编排的「正确行程」，是主观「合理」的客观化锚点。

示例（杭州、周一到达、3 天）：

| 用例 | 硬约束 | 期望 |
|---|---|---|
| 周一闭馆 | 省博物馆 `close_day=1` | 绝不出现在 Day 1（周一） |
| 体力超载 | 特种兵 8 星预算，选 3 个 4 星景点 | 分到 ≥ 2 天，单日不超 8 星 |
| 时间锚点 | 到达 14:00 + 机场 1.5h → Day1 有效 15:30 起 | Day1 不排 17:00 关门的景点 |

### 可执行杭州场景（2026-08-23 首批）

公开资料快照与测试归一化边界见
[`golden-sources-hangzhou.md`](golden-sources-hangzhou.md)。测试运行期间不访问网络。

```powershell
python -m pytest tests/golden -q
python scripts/run_golden_cases.py
```

报告保存到：

```text
docs/test/reports/gate6-golden-latest.json
```

| ID | 场景 | 覆盖 |
|---|---|---|
| HZ-GC-01 | 周一闭馆博物馆自动移至周二 | C1/C2/C6 |
| HZ-GC-02 | 下午抵达不强塞需要半天的上午景点 | C2/C4 |
| HZ-GC-03 | 极端天气迁移室外项目并保留室内项目 | C5/C6 |
| HZ-GC-04 | 固定晚间场次不被晚餐留白挤掉 | C2/C4/C6/S1 |
| HZ-GC-05 | OD 缺失禁止零耗时串联并触发跨天回退 | C6 |
| HZ-GC-06 | 七景点三日混合行程端到端守恒 | C1/C2/C4/C5/C6/S1/S2 |

当前结果：`6/6` 场景通过，硬约束最终违反数为 `0`，重复运行结果一致。
这只是 Gate 6 的 Golden Case 子门禁，不代表数据校验、性能和降级子门禁已经完成。

## 九项数据校验

原始景点记录在转换为求解器 `Attraction` 前，必须逐项通过
[`开放时间数据规范`](../domain/开放时间数据规范.md)的九条规则。

```powershell
python -m pytest tests/solver/test_data_validation.py -q
python scripts/run_data_validation.py
```

默认离线数据快照：

```text
tests/data/hangzhou_attractions_snapshot.json
```

机器可读报告：

```text
docs/test/reports/gate6-data-validation-latest.json
```

当前杭州快照结果：`7/7` 条记录结构合法且可进入求解器，规则 1–9 各自通过 `7/7`。
该结果只证明固定测试快照通过，不代表生产数据库已完成 80–120 个杭州景点的人工校准。

## 性能与规模基准

```powershell
python -m pytest tests/performance -q
python scripts/run_solver_benchmark.py
```

机器可读报告：

```text
docs/test/reports/gate6-performance-latest.json
```

| 场景 | 目标 | 本机 5 次结果 | 状态 |
|---|---:|---:|---|
| N=12 / D=3 | `<30s` | P95 约 33ms | ✅ |
| N=20 / D=7 | `<120s` | P95 约 36ms | ✅ |

每次运行同时验证景点守恒、硬约束违反数为 0，以及包含日期、顺序、到离时间、未排入和
跨天重排的结果指纹一致。该基准是单进程、离线、合成数据的算法基准，不代表 API 并发压测。

当前实现的多日求解仍为顺序执行；规格中的“天内独立求解并行”尚未实现。由于顺序实现已经
远低于 P1 性能门槛，本阶段不为追求形式一致而提前引入并发复杂度，但保留为负载增长后的优化项。

## 降级与反例套件

```powershell
python -m pytest tests/degradation -q
python scripts/run_degradation_cases.py
```

机器可读报告：

```text
docs/test/reports/gate6-degradation-latest.json
```

| ID | 反例/降级场景 | 期望 |
|---|---|---|
| DEG-01 | 30 景点 / 2 天 | 景点守恒，明确 24 个未排入，并提示选择过多 |
| DEG-02 | 所有日期闭馆 | `NO_AVAILABLE_DATE`，逐日保留 C1 原因 |
| DEG-03 | 所有日期极端天气 | 室外景点 `NO_WEATHER_SAFE_DATE` |
| DEG-04 | 单日大面积 OD 缺失 | 不按零耗时串联，无法连接的景点明确未排入 |
| DEG-05 | 晚间场次撞末日离开锚点 | 场次不得突破 C4，明确未排入 |
| DEG-06 | 晚餐完全无空档 | 保留硬可行景点，晚餐标记 `UNSCHEDULED` 并提示 |

当前结果：`6/6` 通过。超时 best-so-far 仍为待验证项，因为当前 `RoutedDay/ItineraryPlan`
尚未暴露 OR-Tools 是否命中时间上限；不得用普通快速成功案例冒充超时证据。

## 报告模板（G7 验证时填）

```
- 硬约束单测通过率：/ 
- Golden Case 通过数：6/6（杭州首批，仍需扩展其他城市与反例）
- 数据校验覆盖率：杭州离线快照 7/7，生产数据待接入
- 性能：N=12/D=3 P95≈33ms；N=20/D=7 P95≈36ms（本机离线合成基准）
- 降级反例：6/6；超时 best-so-far 待补状态元数据
- 用户测试：认可率 %（n=）
```

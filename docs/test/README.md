# 测试方案

> G6 产物。测试不是实现后的阶段，而是与实现交替进行（约束 TDD）。

Gate 7 人类证据在收集前必须按 [`gate7-research-environment.md`](gate7-research-environment.md) 锁定研究环境。`scripts/lock_gate7_environment.py` 固定 Git commit、protocol hash、应用/求解器版本、published 数据快照、数据库 revision 和前端构建哈希；真实 evidence 必须引用 `locked` manifest，原始材料只进入 `.local/gate7/` 或外部受控空间。

R0.2-04 杭州候选目录与覆盖矩阵使用独立门禁：

```powershell
py -3.12 -m pytest tests/data_governance/test_candidate_catalog.py -q
py -3.12 scripts/validate_candidate_catalog.py --json
```

该门禁只证明 candidate 数量、来源绑定、覆盖和关系线索结构有效，不把候选 POI、代表点或覆盖标签升级为 human_verified/published。执行证据见 [`reports/g7-r0.2-04-hangzhou-candidate-coverage-2026-08-29.md`](reports/g7-r0.2-04-hangzhou-candidate-coverage-2026-08-29.md)。

## 测试分层

| 层 | 内容 | 对应目标 |
|---|---|---|
| 单元测试 | C1 闭馆日、C2 入园/开放时间窗、C4 到达/离开锚点、C5 极端天气、C6 真实路网衔接；另测 S1 时长利用、S2 体力均衡与节奏提示 | 「硬约束 100% 通过」与软偏好回归分别机器可证 |
| Golden Case 回归 | 人工构建 3–5 条「专家行程」基准，求解器输出与基准对比 | 防止算法改动「改好局部、改坏全局」 |
| 数据校验测试 | `data_verified` 覆盖率、开放时间格式/范围一致性 | 数据质量门禁 |
| LLM eval | 结构化抽取人工抽检比例 + 解释生成样例评测 | LLM 输出质量 |
| 性能测试 | N=20/D=7 求解 < 2min、典型场景 < 30s 的自动化基准 | 性能目标 |

## Golden Case 定义（核心）

### M1 求解器契约快照

```powershell
python -m pytest tests/solver/test_solver_contract.py -q
python scripts/run_solver_contract.py
```

机器可读快照：`docs/test/reports/solver-p1-contract.json`。当前公开版本为 `solver-p1-v2 / trip-result-v2 / constraints-p1-v5 / parameters-p1-2026-08-26`，历史 `solver-p1-v1 / trip-result-v1` 继续用于不可变 Revision 回放。参数、状态、拒绝码或硬/软约束词汇发生变化时，契约漂移测试必须失败，并要求按 ADR-0009/ADR-0011/ADR-0012/ADR-0013/ADR-0015 升级版本。

### 高德 OD Provider 与 V2 结果映射

自动化测试默认不访问网络，使用固定响应验证高德多模式有向 OD、缓存和失败分类：

```powershell
python -m pytest tests/application/test_gaode_provider.py tests/application/test_gaode_snapshot_script.py tests/application/test_published_json_provider.py tests/application/test_solver_gateway.py -q
```

覆盖范围包括：环境变量读取与 Key 脱敏、缺 Key、步行/公交/驾车解析、进程内及跨进程 JSON TTL 缓存、请求节流、限流、超时、脱敏 `infocode`/pair/mode/time 失败明细、A→B/B→A 独立构建、稳定模式选择、近似降级、缺边、快照构建的显式联网开关和候选坐标门禁，以及 `trip-result-v2` 对真实交通模式、道路距离和降级原因的映射。和风天气回归覆盖三日 forecast 解析、normal/advisory/extreme 映射、来源字段、哈希、限流、非法响应和显式联网开关。JSON 发布 Provider 回归覆盖 SHA-256、防篡改、candidate/published、`human_verified`、坐标来源、天气来源、审计 fixture 拒绝、ID 唯一性、OD basis/version 和完整有向边；正式合并器还拒绝未审核坐标、缺边/回退 OD、天气篡改和城市不一致。Gateway 回归继续覆盖 OD 感知默认分天、`3/3/1` 数量反例、建议时长负载均衡、强近邻保护、日间末节点前往晚间首节点的终端成本、景点守恒和结果哈希稳定。真实联网只允许按 [`gaode-od-snapshot.md`](../ops/gaode-od-snapshot.md) 和 [`qweather-snapshot.md`](../ops/qweather-snapshot.md) 显式启用，不进入常规测试或 Gate 6 离线回归。

生产组合根回归使用 `tests/application/test_production_composition.py`，覆盖环境配置、显式版本要求、正式快照启动、candidate 拒绝和城市不一致 fail-fast。测试不会给生产组合根增加候选放行参数；真实候选 bundle 还需执行一次实物拒绝验证。

### 评审行程接近度（Gate 6）

Golden Case 的硬约束和景点守恒门禁之外，使用 ADR-0007 定义的结构化接近度比较分天、时段、同日组合和相邻顺序。固定项必须全部命中，软接近度初始阈值为 `0.75`；软分不能补偿 C1/C2/C4/C5/C6 或景点守恒失败。

```powershell
python -m pytest tests/solver/test_closeness.py tests/closeness -q
python scripts/run_closeness_report.py
```

报告为 `docs/test/reports/gate6-closeness-latest.json`。报告同时保留逐景点/逐关系的优选值、可接受值、实际值和命中结果，不能只根据综合分判断算法变化。当前杭州案例来源类型是 `PUBLIC_GUIDE_SYNTHESIS`，综合接近度是可重复的技术回归证据，不是领域专家金标，也不能替代 G7 的真实专家评审和用户认可测试。

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
| HZ-GC-07 | 两个日间景点、午餐空档与 18:30 固定表演稳定展开 | C2/C4/C6/S1/S2 |
| HZ-GC-08 | 单个日间景点覆盖下午，真实湖滨 OD、午晚餐与 19:30 固定表演保留 | C2/C4/C6/S1/S2 |

当前结果：`8/8` 场景通过，硬约束最终违反数为 `0`，重复运行结果一致。HZ-GC-07 覆盖“两个日间景点 + 18:30 固定表演”的建议时长扩展、午餐空档和下午展开；HZ-GC-08 使用审核后湖滨真实 OD，覆盖“单个日间景点 + 19:30 固定表演”的下午展开、完整午餐和完整晚餐。
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
该结果只证明 7 点 A6/Gate 6 固定技术快照通过，不代表 Gate 7 数据准备完成。G7-R1 的研究最低目录为约 50–75 个 `human_verified` Place；M1 受控上线目录原则上为 80–120 个，二者都要求进入求解投影的发布字段和时间规则 100% 审核。

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
| N=12 / D=3 | `<30s` | 本机 P95 `<100ms` | ✅ |
| N=20 / D=7 | `<120s` | 本机 P95 `<100ms` | ✅ |

每次运行同时验证景点守恒、硬约束违反数为 0，以及包含日期、顺序、到离时间、未排入和
跨天重排的结果指纹一致。该基准是单进程、离线、合成数据的算法基准，不代表 API 并发压测。

当前实现的多日求解仍为顺序执行；规格中的“天内独立求解并行”尚未实现。由于顺序实现已经
远低于 M1 性能门槛，本阶段不为追求形式一致而提前引入并发复杂度，但保留为负载增长后的优化项。

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
| DEG-07 | 时间上限内已有解 | 返回经最终硬约束复核的 `best_so_far` |
| DEG-08 | 时间上限内无解 | 使用 `SOLVER_TIME_LIMIT` 明确未排入，不伪称 best-so-far |

当前结果：`8/8` 通过。搜索元数据区分 `completed`、`best_so_far`、
`time_limit_no_solution`、`no_solution`、`invalid` 和 `empty`，并保存 initial、reassignment、final
搜索尝试历史；跨天恢复不得覆盖此前发生的超时证据。

## 报告模板（G7 验证时填）

```
- 硬约束单测通过率：/ 
- Golden Case 通过数：8/8（杭州首批，仍需扩展其他城市与反例）
- 数据校验覆盖率：杭州离线快照 7/7，生产数据待接入
- 性能：N=12/D=3、N=20/D=7 本机 P95 均 `<100ms`（精确值见最新报告）
- 降级反例：8/8，含有解超时和无解超时
- 用户测试：认可率 %（n=）
```

## Gate 7 人类证据准备

Gate 7 不复用 Gate 6 的自动化通过口径。当前验证方案、表单和机器协议：

- [`gate7-validation-plan.md`](gate7-validation-plan.md)：R0–R3 分段、样本、任务、指标、严重度和决策规则；
- [`gate7-expert-review-form.md`](gate7-expert-review-form.md)：领域专家独立评分与 blocker 登记；
- [`gate7-user-test-script.md`](gate7-user-test-script.md)：形成性/确认性主持脚本和标准 assistance；
- [`gate7-protocol-v1.json`](gate7-protocol-v1.json)：预注册 H3/H11 阈值、角色、严重度、归因和隐私字段；
- [`gate7-data-deployment-readiness-plan.md`](gate7-data-deployment-readiness-plan.md)：R0.2 杭州研究数据、R0.3 服务器 H5 和 R0.4 内部 dry run 门禁；
- [`../ops/gate7-controlled-h5-docker-deployment.md`](../ops/gate7-controlled-h5-docker-deployment.md)：受控 H5 的 edge/API/迁移/MySQL/Redis 全容器拓扑、Compose 生命周期和发布/恢复门禁；
- [`gate7-research-environment.md`](gate7-research-environment.md)：Git、数据、求解版本、数据库迁移和前端构建的收集前锁定；
- [`gate7-evidence-example.synthetic.json`](gate7-evidence-example.synthetic.json)：只用于演示数据格式，永远不能作为真实证据。

校验和匿名聚合命令：

```powershell
python scripts/run_gate7_report.py `
  --protocol docs/test/gate7-protocol-v1.json `
  --environment-manifest .local/gate7/<study_environment_id>/environment.json `
  --evidence .local/gate7/<study_id>/evidence.json `
  --output docs/test/reports/gate7-<study_id>-aggregate.json
```

汇总器会拒绝 protocol hash 漂移、非 locked/不匹配的真实研究环境、缺失知情同意、重复 H3 主指标、未知参与者、非法严重度/归因和敏感字段名。内部/排除样本不进入 H3 分母；`synthetic_fixture=true` 的数据只能得到 `synthetic_only`。单个 study 报告不会直接输出“Gate 7 全部通过”，因为 H2、H3、H11 需要不同证据阶段。

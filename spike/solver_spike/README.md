# G3 Solver Spike（分层求解可行性验证）

> 工作流 G3 阶段的风险前置验证。**代码可丢弃，只求结论。** 结论已落 ADR-0001。

## 验证的问题

1. 「K-Means 聚类分天 → 天内 TSP-TW → 约束校验 → 回溯」这条分层路线，在真实规模数据上**逻辑能否跑通**？
2. 硬约束（闭馆日、开放时间、体力预算、时间锚点、天气）能否被**确定性机制**保证，而非依赖 LLM？
3. OR-Tools 天内 TSP-TW 在典型规模上**能否 <30s 收敛**？
4. 纯经纬度 K-Means 分天是否会产生**严重不均衡**？

## 运行

```bash
cd spike/solver_spike
python solver.py            # 贪心版完整分层求解（零依赖，仅 numpy）
python test_solver.py       # 7 个硬约束单测
python benchmark_ortools.py 12 3   # OR-Tools TSP-TW 收敛实测
python benchmark_ortools.py 20 7
```

## 成功判据（Gate 3 退出准则）

- [x] 分层求解逻辑跑通，输出可读行程
- [x] 硬约束单测全绿（闭馆日 / 时间窗 / 锚点 / 天气 / 体力检测）
- [x] 收敛达标：OR-Tools 单日 TSP-TW **毫秒级**（N=12/D=3 max 1.6ms；N=20/D=7 max 1.4ms）
- [ ] K-Means 分组均衡性可接受 —— **未通过，需替换**（见下方「已知弱点」）

## 已知弱点（Spike 结论，见 ADR-0001）

1. **纯经纬度 K-Means 不感知每日均衡**：会聚出「某天景点多/体力爆表」的分组，靠 `rebalance` 事后打补丁。**结论**：生产换 capacity-aware 聚类（限制每类景点数/能量）或 DBSCAN。
2. **单车辆 TSP-TW 必须访问所有节点**：K-Means 把 5 个景点塞进一天（总时长超 9:00–21:00）→ 无可行解。**结论**：生产用 `AddDisjunction` 允许丢弃放不下的景点，配合「每日上限」前置提示。
3. **贪心启发式是局部最优**：先到先得，漏排景点，OR-Tools 能排入更多。**结论**：生产用 OR-Tools 替换 `solve_day_tsp_tw`（映射见技术选型文档 4.5）。
4. **OD 矩阵是直线距离 × 绕行系数**，非真实路网耗时。**结论**：生产接高德路径规划 API 预计算（见技术选型文档 6.2）。
5. **Slack 设置教训**：`slack_max` 设 1440（允许等 24h）会撑爆搜索空间（2 景点竟跑满 30s）。生产 slack 上限按「最大等待开门」设 240 即可。

## 下一步

1. G4 详细设计：capacity-aware 聚类 + OR-Tools + disjunction。
2. Data Quality Spike（待高德 API key）：20 个真实杭州景点量化 LLM 抽取准确率。
3. 「每日上限」前置提示纳入 P1 交互设计（关联 H6/H7）。

## 结论去向

- ADR：[docs/decisions/ADR-0001-spike-solver.md](../../docs/decisions/ADR-0001-spike-solver.md)
- 假设登记册：H3 仍「未验证」，本 Spike 只验证了「可行」，未验证「比人排更合理」。

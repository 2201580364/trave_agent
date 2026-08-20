---
name: solver-dev
description: 求解器开发规范：分层建模约定 + 约束 TDD + Golden Case 回归，守住硬约束 100% 通过（G5 阶段）
---

# 求解器开发技能

> 求解器是「最硬技术壁垒」，开发必须约束 TDD，测试先行。

## P1 分层求解流程（已确认，见技术选型文档）

```
Step1 地理聚类（K-Means，K=D）→ Step2 天内排序（TSP-TW）→ Step3 约束校验与回溯 → Step4 时间填充 + LLM 解释
```

## 开发顺序（约束 TDD）

1. **先写约束单测**，再写实现。每条硬约束一条测试：
   - `close_day`：周一闭馆绝不出现在周一
   - 开放时间窗：到达 + 游览时长 ≤ 关闭时间
   - 体力预算：每日 `sum(energy) ≤ 模式预算`
   - 时间锚点：Day1 起始 = 到达 + 场站耗时；DayN 结束 = 离开 − 提前量
2. **实现求解器**，跑通单测。
3. **跑 Golden Case**：对照 [docs/test/](../../../docs/test/README.md) 的专家行程基准。
4. **性能基准**：N=20/D=7 < 2min，典型 < 30s。

## 建模约定

- 时间内部统一用「当天 0 点起分钟数」。
- 目标函数必须显式定义（P1 建议：`min(总通勤耗时 + λ·跨区惩罚 + μ·体力不均衡)`，λ/μ 为待调参数，记入 ADR）。
- 已知弱点：纯经纬度 K-Means 不感知每日均衡，需回溯/再平衡步骤（Spike 已演示，见 [spike/solver_spike/](../../../spike/solver_spike/)）。

## 遵守规则

见 [.claude/rules/solver.md](../../rules/solver.md)。

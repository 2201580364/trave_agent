---
description: 对最不确定的技术点做可丢弃原型（Spike），先证明可行再投入
argument-hint: <验证问题，如 solver 分层求解可行性>
---

调用 `spike` skill（见 [.claude/skills/spike/](../skills/spike/SKILL.md)），按模板对 `$ARGUMENTS` 做技术可行性验证。

本项目两个必做 Spike：
1. Solver Spike（参考 [spike/solver_spike/](../../spike/solver_spike/)）
2. Data Quality Spike

输出结论写入 `docs/decisions/`，含「何时推翻重议」。

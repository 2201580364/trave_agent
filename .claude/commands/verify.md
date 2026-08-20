---
description: 执行假设验证并复盘，回写假设登记册
---

调用 `verify` skill（见 [.claude/skills/verify/](../skills/verify/SKILL.md)）：

1. 执行验证（自动化测试 + 用户测试 + 埋点指标）。
2. 采集证据：硬约束单测通过率、Golden Case、性能、认可率、分享率。
3. 对每个未达标的假设做失败归因（数据/算法/交互）。
4. 回写 [docs/assumptions.md](../../docs/assumptions.md) 的 `状态` + `证据`。

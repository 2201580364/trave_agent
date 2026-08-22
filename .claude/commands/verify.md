---
description: 执行假设验证并复盘，回写假设登记册
---

调用 `verify` skill（见 [.claude/skills/verify/](../skills/verify/SKILL.md)）：

1. 执行验证（Spike、自动化测试、专家评审、用户测试、埋点指标需分别记录，不得混为同级证据）。
2. 采集证据：原始路径、样本量、数据区间、硬约束单测、Golden Case、性能、认可率、分享率与局限。
3. 对每个未达标的假设做失败归因（数据/算法/交互）。
4. 只有满足假设预设证据条件时才改为「已证实/已推翻」；技术测试不得替代用户认可证据。否则保持「验证中」并记录部分结论。
5. 回写 [docs/assumptions.md](../../docs/assumptions.md) 的 `状态` + `证据`。

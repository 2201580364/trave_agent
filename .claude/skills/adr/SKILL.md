---
name: adr
description: 写架构决策记录（ADR），含备选方案权衡与「何时推翻重议」触发条件（G4 阶段）
---

# 架构决策记录技能

## 何时写 ADR

- 新增第三方依赖 / 服务
- 改变求解目标函数
- 选型变更（如方案 B → 方案 A）
- Spike 得出需要改变路线的结论

## 模板

见 [docs/decisions/0000-adr-template.md](../../../docs/decisions/0000-adr-template.md)。

## 关键要求

**必须写「何时推翻重议（触发条件）」**——这是 ADR 与普通备忘的区别。例：技术选型文档中「P2 引入住宿优化时重新评估方案 A（多车辆建模）」就是一条触发条件。

## 编号与落盘

`docs/decisions/ADR-0001-<slug>.md` 递增编号。

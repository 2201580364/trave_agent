---
description: 把功能需求转成带 Given/When/Then 验收标准的需求规格
argument-hint: <功能名，如 trip-solver>
---

调用 `spec` skill（见 [.claude/skills/spec/](../skills/spec/SKILL.md)），把 `$ARGUMENTS` 对应的功能写成需求规格，落盘到 `docs/specs/<功能名>.md`。

默认从「一键生成分日行程」（trip-solver，承载 H3）开始。

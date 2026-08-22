# 决策与可追溯性规则

1. **新增第三方依赖必须写 ADR**：引入新的库/服务前，在 [docs/decisions/](../../docs/decisions/) 记录决策（含「何时推翻重议」触发条件）。
2. **每个 PR 关联假设编号**：PR 描述必须关联 `H-x`（[docs/assumptions.md](../../docs/assumptions.md)）或需求编号；无关联则说明为何无需关联。
3. **假设状态变更需回写**：验证有了结论，回写 `docs/assumptions.md` 的 `状态` 与 `证据` 列（用 G7 回写模板）。
4. **领域规范变更需通知双方**：改动 [docs/domain/](../../docs/domain/) 规范，需同时考虑对「数据标注」和「求解器」两处的影响。
5. **ADR 变更需传播**：按 [Gate 规范](../../docs/process/gates.md) 检查 context、rules、skills、agents、specs、domain、tests 与 Golden Cases，避免 AI 控制文件停留在旧决策。

# trave_agent 项目记忆

## 文档治理架构（2026-09-05 S1 文档手术确立）

- **状态分层**：L0 正本=AGENTS.md（CLAUDE.md 为薄指针，改内容只改 AGENTS.md 再跑 `python scripts/sync_agents_docs.py`）；L1 滚动状态=docs/process/CURRENT.md（唯一「当前节点」入口，每轮更新，≤150 行）；L2 稳定路线/规范；L3 历史归档=docs/process/status-archive/ 按月切片（永不全文读）。
- **project-status.md 已降格为归档账本头**：只追加、含蒸馏后的「明确未完成」清单；每轮结束更新 CURRENT.md 而非追加全量记录。
- **ADR 编号**：ADR-0020=admin-web 技术栈（原 0 字节已补写）；节假日历物化 ADR 已改号 ADR-0023；新增 ADR 从 0024 起编。
- **改造实施方案**：docs/process/transformation-plan.md，S1 已完成（2026-09-05），下一步 S2 check_docs.py 文档门禁（防治理工具自指漂移：每份新清单必须有 check_docs 对应校验项）。

## 用户核心约定

- **文档改造≠纯目录格式调整**：必须先做数据清洗与过滤（去重/去过期/去矛盾——被后续轮次推翻的不能带进新文档、散落事实收敛到唯一权威位置），再重构；整理后语义必须与整理前严格一致，项目方向不变。
- 语义一致性验证方式：关键事实（测试基线、提交哈希、迁移版本、数据规模、节点表述）逐项与原账本核对。

## 项目关键事实（2026-09-05 有效）

- 节点：M1 后段 / Gate 7 / OM1 / G7-R0.2-05-03 + R0.2-07；O17 已提交 c2ea117。
- 基线：pytest 424/424、admin-web Vitest 39/39、Alembic 至 0015；服务器 MySQL 停 0002 待迁移。
- 研究库 .local/research.db：72 条候选（3 published / 69 candidate）；12 条人工审核批次待处理。
- 求解器契约：solver-p1-v2 / trip-result-v2 / constraints-p1-v5 / parameters-p1-2026-08-26。

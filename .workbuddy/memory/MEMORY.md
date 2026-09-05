# trave_agent 项目记忆

## 文档治理架构（2026-09-05 S1 文档手术确立）

- **状态分层**：L0 正本=AGENTS.md（CLAUDE.md 为薄指针，改内容只改 AGENTS.md 再跑 `python scripts/sync_agents_docs.py`）；L1 滚动状态=docs/process/CURRENT.md（唯一「当前节点」入口，每轮更新，≤150 行）；L2 稳定路线/规范；L3 历史归档=docs/process/status-archive/ 按月切片（永不全文读）。
- **project-status.md 已降格为归档账本头**：只追加、含蒸馏后的「明确未完成」清单；每轮结束更新 CURRENT.md 而非追加全量记录。
- **ADR 编号**：ADR-0020=admin-web 技术栈（原 0 字节已补写）；节假日历物化 ADR 已改号 ADR-0023；新增 ADR 从 0024 起编。
- **改造实施方案**：docs/process/transformation-plan.md，S1/S1.5/S2/S3 已完成（2026-09-05），下一步 S4 依赖锁定（无前置可并行）或 S5 脚本契约；S3-6 分支保护需用户在 GitHub Settings 手动开启。
- **机器再生产物不放 docs/**：gate6-*.json、solver-p1-contract.json 位于 var/reports/（gitignored），6 个 scripts/run_*.py 默认输出路径已同步；报告归档切片在 docs/test/reports/archive/ 按月存放。

## 用户核心约定

- **文档改造≠纯目录格式调整**：必须先做数据清洗与过滤（去重/去过期/去矛盾——被后续轮次推翻的不能带进新文档、散落事实收敛到唯一权威位置），再重构；整理后语义必须与整理前严格一致，项目方向不变。
- 语义一致性验证方式：关键事实（测试基线、提交哈希、迁移版本、数据规模、节点表述）逐项与原账本核对。
- **npm 一律用国内镜像源** `--registry=https://registry.npmmirror.com`（官方源在本机网络极慢/卡死）；大依赖树安装交给用户手动执行更高效。

## 项目关键事实（2026-09-05 S3 完成后有效）

- 节点：M1 后段 / Gate 7 / OM1 / G7-R0.2-05-03 + R0.2-07；O17 已提交 c2ea117；最新提交 89ea3de。
- 基线：pytest 465/465、ruff check 全仓 0 违规（B008 豁免 FastAPI 惯用法）、admin-web Vitest 41/41 + typecheck + build 全过、frontend typecheck 过、golden 8/8、Alembic 至 0015；服务器 MySQL 停 0002 待迁移。
- CI：.github/workflows/ci.yml 三 job（backend/admin-web/frontend）；mypy 全量债未入 CI（见 ci-troubleshooting.md 已知债务节）；ruff format 漂移 103 文件 non-blocking。
- 研究库 .local/research.db：72 条候选（3 published / 69 candidate）；12 条人工审核批次待处理。
- 求解器契约：solver-p1-v2 / trip-result-v2 / constraints-p1-v5 / parameters-p1-2026-08-26。
- admin-web/package-lock.json 已重新生成（原 0 字节）；@testing-library/dom 为必需 peer。

## S1.5 进展（2026-09-05）

- S1.5-1 已完成：api-contract.md V2.10 章节编号规整（1–15 单调、双 "## 12" 消除、O09 回流 §15.2 内、无编号追加节编为 15.2.1–15.2.4）；差异清单在 docs/specs/api-contract-endpoint-diff-2026-09-05.md，**待人工裁决**：doc-only 3 条（POST /admin/candidates、GET /admin/places/{place_id}、POST /admin/places/{place_id}/retirements——注意 retirements 与 R0.2-07 发布即退役语义冲突，倾向删或改写）+ 未登记实现 3 条（holiday-calendar-sync-capability、dashboard-summary、GET place-revisions/{id}）+ retry(P1) 标注未排期 + health 探针写入 §2。
- 无外部文档按章节号引用 api-contract（已 grep 验证），重排无断链；check_docs.py 全过。S1.5-2～S1.5-6 未开始。

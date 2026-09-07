# CURRENT — 当前状态滚动快照

> 唯一的「现在」入口。每轮任务结束时更新本文件；历史细节看 [status-archive/](status-archive/)，跨里程碑稳定路线看 [project-roadmap.md](project-roadmap.md)。

- 更新时间：2026-09-07
- 当前节点：`M1 后段 / Gate 7 / OM1 / G7-R0.2-05-03 + R0.2-07（多地点审核基线，R0.2-09 O17 已提交）；transformation-plan S1–S6 已完成（S6 合并 941578e/fae014e），S8-1 进行中，S7 等待数据批次（12 条中 2 条已发布）`
- 稳定测试基线：后端 pytest `465/465`（424 存量 + 33 新增测试 + 8 golden 独立跑全过）；ruff check 全仓清零；admin-web Vitest `41/41` + typecheck + production build 全过（`@testing-library/dom` peer 缺失已补）；Alembic 迁移链至 `0015_holiday_exception_provenance`
- 最近提交基线：`fae014e feat(s6): 并行开发试点——协作规范 v2 与 admin 会话持久化`；`941578e feat(scripts): S5 脚本契约标准化`

## 最近三轮已完成（一行一项）

- 2026-09-07 S6 并行开发试点（transformation-plan，本会话）：协作规范落地 `.claude/rules/parallel-workflow.md` 并经复盘升版 v2（一会话=一分支=一能力域 + In-flight 登记 + 迁移/共享库互斥 + 合并队列纪律 + 基线口径/验证纪律）；AGENTS.md 加 2 行硬规则（sync + check_docs 全过）；In-flight 区启用（S5 + S6-C 双登记）；试点任务 C=admin 会话持久化：后端 admin_sessions 本就持久化，前端 token 由内存 ref 改 sessionStorage + 挂载 /me 恢复（fail-closed）+ 3 个新测试；全量回归零回退（pytest 479/479[465+S5 新增 14]、Vitest 44/44[41+3]、tsc、build、golden 8/8、check_docs、layering 全过）。

- 2026-09-07 S5 脚本契约标准化 + 工具安全分级（transformation-plan）：`.claude/rules/script-contract.md`（契约七条 + L1/L2/L3 三级分类 + scripts/ 全量 26 脚本分级登记）；首批 5 脚本达标改造（report_research_readiness 补 --json、audit_catalog_boundaries 补缺库 fail-closed 退出 1、validate_candidate_catalog 0/1/2 语义 + 修复 SourceRegistryError 未捕获崩溃、run_golden_cases 补 --json + 门禁失败 1→2、import_candidate_revisions 补 --json + 修复空库 dry-run 崩溃）；`tests/scripts/test_script_contracts.py` 10 项契约测试全过；同步更新存量断言（status "valid"→"ok"）。
- 2026-09-05 api-contract V2.11 端点差异裁决落地（S1.5-1 ②收尾，本会话）：6 条全部裁决——删除 `POST /admin/candidates`（与 `POST /places/{place_id}/revisions` 重复）；删除独立 `POST /admin/places/{place_id}/retirements`，§15.2 新增「发布版本退役语义」声明（退役由 publications 单条/批次链路发布新版时同事务原子完成，不提供绕过发布门禁的退役通道）；`GET /admin/places/{place_id}` 移入新增 §15.2.0「计划端点」小节；补登 3 个已实现端点（`GET /place-revisions/{revision_id}`、`GET /dashboard-summary`、`GET /holiday-calendar-sync-capability`）；retry（P1）标注未排期；health 探针写入 §2.1.1 运维探针。check_docs 全过。
- 2026-09-05 S4 依赖锁定 + 文档对齐实现（transformation-plan）：`uv.lock`（141 包）入库，`uv sync` 后全量 pytest 465/465 验证；升级政策 ADR-0024（5 步升级流程 + 4 个行为敏感依赖 ortools/sqlalchemy/alembic/fastapi 清单，golden 差异即停）；frontend/admin-web Node engines 统一为 `>=22 <25`、npm `>=10 <12`（frontend package-lock engines 同步再生，diff 仅 4 行，typecheck 过）；AGENTS.md 技术栈表核对实现（Celery/COS/LLM 虚报 S1 已清，本项补 Python 版本口径与 uv.lock 引用），sync 脚本重派生 CLAUDE.md。
- 2026-09-05 S3 CI 流水线 + 分层断言（transformation-plan）：`.github/workflows/ci.yml` 三 job（backend: ruff+pytest+golden+layering+docs；admin-web: vitest+tsc+build；frontend: tsc）；自研 `scripts/check_layering.py` 四规则 + 组合根豁免 + 8 项契约自测；ruff 存量 170→0（formatter 批量清偿，全量 pytest 465/465 验证零语义破坏）；修复 P0-1 乱码正则（中文敏感词「私钥/密码/令牌」恢复拦截 + 17 项回归测试）；CI 排查指引 `docs/process/ci-troubleshooting.md`。
- 2026-09-04 版本退役语义修复（R0.2-07）：发布新版本时原子退役同一地点旧 `published` Revision/Projection（转 `retired`、`solver_eligible=false`），历史保留但不再进入用户端求解目录；已修复 research.db 浙江省博物馆孤山馆区旧第 1 版；新增持久化回归。
- 2026-09-03 O17 可执行同步闭环提交（`c2ea117`）：中国政府网公告发现器、受限域名获取器、供应商中立 OpenAI-compatible 抽取适配器、独立 `travel-agent-holiday-worker` 进程（有限批次/周期轮询/优雅停止/lease 恢复/同年度运行锁/指数退避）；管理页面含任务详情、预览数据确认弹窗、取消端点与 AI/系统执行过程时间线；真实 2024 年同步已完成人工验收；迁移 0014/0015。
- 2026-09-03 多地点审核基线（G7-R0.2-05-03/R0.2-07）：`report_research_readiness.py` 只读工具；修复两个批量审核前门禁缺口（编辑基础事实/新增证据清除导入期核验标记；Revision 审核通过要求六项准备度全部采集且核验）；研究库母集 72 条（published=3、candidate=69）；选定下一轮 12 条人工审核批次（`hz-cand-003/006/010/013/014/020/024/027/042/045/048/052`）。

## 下一步（按顺序）

1. 完成上述 12 条的人工补证与 reviewer 逐项审核，再执行 Projection、批次发布和用户端可见性回归。
2. 稳定后扩展研究目录至 50–75 条 `human_verified`（G7-R1 研究最低目录门槛）。
3. 实施 R0.2-06 按需真实 OD 子图（候选过滤→锚点真实 OD→缓存→不可变子图 hash→Revision 回放，缺边不填 0）。
4. 进入 R0.3 服务器全栈 Compose/HTTPS/环境锁定；期间 G1 真实用户发现研究补证可与 R0.2–R0.4 并行、R1 前关闭。

## 活跃风险

- Gate 1 存在真实用户研究补证债务：无真实访谈纪要与可追溯结论，M1 最终决策前必须完成 8–10 名目标用户发现研究，不得倒填。
- 历史账本记载的测试计数互相矛盾（352/363/367/370/…/432），以最新 424/424 + 39/39 为准；旧计数属阶段性快照，不代表回退。
- 全仓 strict mypy 存量类型债（数百条/数十文件，mypy 2.3 比建仓时代更严格），未纳入本轮范围；CI 暂不跑 mypy 全量（见 docs/process/ci-troubleshooting.md 已知债务节）；ruff check 债务已清零（2026-09-05），`ruff format` 历史漂移 103 文件为 non-blocking。
- 服务器真实 MySQL 仍停在已验收的 `0002_anonymous_identity` 基线，下次应用发布前必须依次执行 0003→0015 并重新验证 readiness、备份与隔离恢复。
- H1–H12 全部「未验证」；自动化测试、Chrome 验收或团队内部判断均不能冒充 H3/H11 的真实用户证据。
- Windows 偶发 `WinError 10055` 套接字错误为环境 flaky（隔离复跑即过），非业务回归。

## In-flight 区（并行任务登记）

| 任务 | 分支 | 触碰文件 | 状态 |
|---|---|---|---|
| S8-1 frontend Vitest 补测 | dev（S8 会话） | `frontend/`（vitest.config.ts 已建、待装依赖与写测试） | 进行中（2026-09-07；纯 frontend 触碰面，不动 ci.yml——CI 集成留给 S8-2 统一处理） |

> S1–S6 全部完成并已合并销账（S5=`941578e`、S6=`fae014e`）；S7 硬前提「R0.2-07 数据批次完成」未满足（12 条批次 2 条已发布、10 条 needs_evidence），暂不入队。

## 关键事实速查

- 研究库 `.local/research.db`：72 条杭州候选（published=3：平湖秋月、浙江省博物馆孤山馆区[第 2 版]、西湖音乐喷泉表演；candidate=69），目录边界审计通过。
- 求解器契约：`solver-p1-v2 / trip-result-v2 / constraints-p1-v5 / parameters-p1-2026-08-26`；历史 Revision 不迁移、不覆盖、不原地重算。
- Gate 7 protocol 规范化 SHA-256：`b791f0558dfc93af4cc919ec6dd9b09d1251f8f1d54b7bc0bb8809eade742d89`。
- 正式发布 bundle：`var/published/hangzhou-published-2026-08-27-v1.json`（7 景点 human_verified 坐标 + 42/42 高德 OD + 真实和风三日天气）。
- 本机禁止部署/启动 MySQL/Redis；本地开发组合根用明确标注的近似 fixture，生产组合根只加载严格验证的 published 快照。

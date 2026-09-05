# trave_agent 改造实施方案（AI 控制面 + 工程基础设施）

- 版本：V1.0
- 日期：2026-09-05
- 上游依据：`docs/test/reports/architecture-review-2026-09-04.md`（全库技术评审）+ 跨会话知识库/控制面治理建议（已核实采纳）
- 总目标：让知识库自维护、开发可多会话并行、质量门禁机器化，为 R0.3 服务器部署和 M2 多城市扩展建立健全基座
- 执行原则：每阶段有明确退出准则，不满足不进下一阶段；每个任务独立提交边界；**阶段顺序不可调换**（依赖关系已标注）

---

## 阶段总览与状态

| 阶段 | 名称 | 状态 | 前置依赖 | 预估工作量 |
|---|---|---|---|---|
| S1 | 文档手术：分层加载 + 正本派生 | **已完成（2026-09-05）** | 无 | 0.5–1 天 |
| S1.5 | S1 收尾补丁：specs/product 清洗 + 测试报告归档 | **已完成（2026-09-05）** | S1（已完成） | 0.5–1 天 |
| S2 | check_docs.py 文档门禁 | **已完成（2026-09-05）** | S1 | 1 天 |
| S3 | CI 流水线 + 分层断言 | **已完成（2026-09-05；S3-6 分支保护待仓库设置）** | S2 | 1–2 天 |
| S4 | 依赖锁定 + 文档对齐实现 | **已完成（2026-09-05）** | 无（可并行） | 0.5 天 |
| S5 | 脚本契约标准化 + 工具分级 | **未开始** | S2 | 1 天 |
| S6 | 并行开发试点 | **未开始** | S3 | 1–2 天 |
| S7 | 上帝类拆分（代码健康切片） | **未开始** | S3、R0.2-07 数据批次完成 | 1–2 周 |
| S8 | 用户端补测 + 契约对照 | **未开始** | S3 | 3–5 天 |

> 状态取值：`未开始` → `进行中` → `已完成` / `阻塞`（附原因）。每完成一项，更新本表并在 CURRENT.md 登记一行。

---

## S1 文档手术：分层加载 + 正本派生

**目标**：冷启动从「全量读 40k+ token」降到约 3k token；消灭同一事实多处复述。

| # | 任务 | 产出 | 状态 |
|---|---|---|---|
| S1-1 | `project-status.md`（1254 行）按月切片到 `docs/process/status-archive/2026-08.md` 等；原文件只保留文件头说明「本文件是归档账本，只追加、永不全文读，当前状态看 CURRENT.md」 | 归档切片 + 改造后的账本头 | 已完成（切片 2026-08.md 893 行 / 2026-09.md 358 行；账本头含蒸馏后的「明确未完成」清单） |
| S1-2 | 新建 `docs/process/CURRENT.md`（≤150 行）：当前节点 / 最近 3 轮已完成（一行一项，含验证数据）/ 下一步 / 活跃风险 / **In-flight 区**（并行任务占用登记：分支名、触碰文件、状态） | CURRENT.md | 已完成（60 行，含关键事实速查） |
| S1-3 | CLAUDE.md 瘦身为 L0（≤120 行）：身份一句话、四条核心原则、关键约定、**任务类型→阅读路由表**、技术栈速览（对齐实现，删 Celery/COS/行程 LLM 虚报）；易变状态全部移除，指向 CURRENT.md | 新 CLAUDE.md | 已完成（CLAUDE.md 改为薄指针，内容正本移至 AGENTS.md） |
| S1-4 | 新建 `AGENTS.md` 作为 L0 正本（内容=S1-3 产物）；CLAUDE.md 改为薄指针（「读 AGENTS.md」）；`scripts/sync_agents_docs.py` 一键同步（后续 Cursor rules 也从它派生） | AGENTS.md + 同步脚本 | 已完成（AGENTS.md 86 行 + sync 脚本含 `--check` 模式） |
| S1-5 | README.md「当前阶段」段改为指向 CURRENT.md，不自行复述节点 | 更新 README | 已完成 |
| S1-6 | ADR 修复：`ADR-0020-admin-web-ui-stack.md`（0 字节空文件）补写或删除改号；解决 ADR-0020 编号冲突（holiday-calendar-materialization 改号 ADR-0023 并全库更新引用）；ADR 索引表增加 `supersedes` 列 | 修复后的 ADR 集 + 索引 | 已完成（ADR-0020 补写 34 行；holiday-calendar 改号 ADR-0023 并更新 ADR-0021 引用；supersedes 列随 S2 check_docs 落地） |
| S1-7 | `00-index.md` 增加 L0–L3 分层说明与新会话阅读顺序（先 AGENTS.md → CURRENT.md → 按任务路由） | 更新 00-index.md | 已完成 |

**退出准则**：新会话只需读 AGENTS.md + CURRENT.md（≤270 行）即可接续工作；`grep "当前节点"` 在 CLAUDE/README/CURRENT 中各至多一处且一致；无 0 字节 ADR、无编号冲突。

---

## S1.5 S1 收尾补丁：specs/product 清洗 + 测试报告归档

**目标**：把 S1 的清洗蒸馏原则覆盖到评审发现的三个遗留目录，消灭文档与实现的现存矛盾。上游依据：2026-09-05 文档目录清洗蒸馏评审。

**执行原则**（沿用 S1 用户核心约定）：文档改造≠纯目录格式调整，必须先做数据清洗与过滤（去陈旧/去矛盾/收敛到唯一权威位置），整理后语义与整理前严格一致；decisions/、domain/、ops/、research/、assumptions.md、00-index.md、process/ 经评审明确不动。

| # | 任务 | 内容 | 状态 |
|---|---|---|---|
| S1.5-1 | specs/api-contract.md 结构修复（1481 行） | ① 修复章节编号错乱（现存两个 "## 12"，O09 章节误插在 4/5 节之间，O05/O06 等无编号追加节回流进章节体系）；② 脚本化对比文档端点清单 vs `interfaces/http/` 实际 `@router.*` 路由（60+ 条），产出差异清单人工裁决补齐/删除 | 已完成（2026-09-05：编号规整为 1–15 单调递增，O09 回流 §15.2、无编号节编为 15.2.1–15.2.4；差异清单 docs/specs/api-contract-endpoint-diff-2026-09-05.md；**差异 6 条已全部人工裁决并落地 V2.11**——删除 POST /admin/candidates 与独立 retirements 端点（退役语义改写为 publications 链路原子退役声明）、GET /admin/places/{place_id} 移入 §15.2.0 计划小节、补登 place-revisions GET/dashboard-summary/sync-capability 三端点、retry 标注未排期、health 探针写入 §2.1.1；check_docs 全过） |
| S1.5-2 | specs/data-model.md 漂移核对（1112 行） | 对照 models 层实际字段做一轮核对，过时字段/枚举修正（同 S1.5-1 方法，允许脚本辅助） | 已完成（2026-09-05：V3.0→V3.1；头部状态行更新至 0001–0015 且 16.6 标为已实现；line 195 time-preview 已开放；§13 迁移链补全 0008–0015 且 readiness 目标改 0015；§16 导语纳入 0011；§16.3 表名修正为 publication_batches/publication_batch_items/research_snapshots 并补发布即退役语义；§16.6 改写为已实现（0014/0015）并按 holiday_calendar.py 实际字段对齐（calendar_year、run_lock_key 运行锁/lease 语义、ensure_builtin seeds 分离）；check_docs 全过） |
| S1.5-3 | product/ 陈旧声明清除 | 清除 7 处「管理 Web 与地点审核仍待实现」类被实现推翻的声明（O18设计×2、功能模块设计×3、交互流程与状态机×1、应用代码架构×1）；落地「现状声明单一权威位置」原则：现状类表述只允许出现在 CURRENT.md，product 文档改为设计意图表述或指向 CURRENT.md；功能模块设计与管理端功能模块设计的交叉内容收敛为引用 | 已完成（2026-09-05：O18设计×2（当前状态行+实施计划 O17 行）、交互流程与状态机×1、应用代码架构×1、信息架构与UI O17 行、产品功能完整性审查结论行改为指向 CURRENT.md；功能模块设计实现状态段/5.2.3/6.4.4 改为设计基线表述并指向 CURRENT.md；管理端功能模块设计头部现状两行收敛为指向 CURRENT.md；check_docs 全过） |
| S1.5-4 | product/应用代码架构设计.md 对照现状修正（933 行） | 架构描述对齐已落地分层（domain/solver/application/infrastructure/interfaces + check_layering.py 四规则） | 已完成（2026-09-05：V1.5→V1.6；§1 Gate 7 增量边界改写为落地对齐说明（实际目录 admin.py/domain/admin/application/admin/infrastructure/database/holiday_sync/composition、check_layering 四规则 119 文件 0 违规）；§4.2 目录树按实际结构重写并标注 A4 推荐来源差异；governance/admin_http/bootstrap/container 旧命名清除；§17.2/17.3 过时迁移链表述改为指向 data-model §13 与 head 0015） |
| S1.5-5 | test/reports/ L3 归档切片（27 文件） | 复用 S1 L3 模式：reports/ 留 README 索引 + 最新报告（architecture-review-2026-09-04.md 等活跃文档），其余按月移入 reports/archive/2026-08/ 等；报告本身只搬移不改语义 | 已完成（2026-09-05：24 份 2026-08 报告 git mv 至 archive/2026-08/；保留 README 索引 + architecture-review + 2 份 9 月活跃报告；ops 文档 4 处归档路径引用同步更新） |
| S1.5-6 | gate6-*.json 移出文档库 | 机器再生产物（5 个）移至 var/ 或纳入 .gitignore，docs/ 不放可再生输出 | 已完成（2026-09-05：gate6-*.json ×5 + solver-p1-contract.json 移至 var/reports/（var/ 已在 .gitignore，json 保持本地不入库）；6 个 scripts/run_*.py 默认输出路径同步更新；test/README 与 solver-p1-contract.md 引用路径同步） |

**退出准则**：api-contract.md 无重复编号、文档端点清单与路由实现一致（或差异均有 ADR/CURRENT 佐证）；product/ 无「已实现却仍写待实现」类矛盾、现状声明仅 CURRENT.md 一处；reports/ 根目录仅剩索引与活跃文档；check_docs.py 全过。

---

## S2 check_docs.py 文档门禁

**目标**：文档漂移靠脚本拦截，不靠自觉。

| # | 任务 | 检测项 | 状态 |
|---|---|---|---|
| S2-1 | 新建 `scripts/check_docs.py`（风格对齐 audit_catalog_boundaries.py：fail-closed、退出码 0=通过 / 2=违规 / 1=错误、`--json` 输出） | 见 S2-2~S2-6 | 已完成（4 项检测 + 8 项契约自测全过） |
| S2-2 | 检测项①：空 ADR（<10 行视为空）、ADR 编号复用 | 违规清单 | 已完成 |
| S2-3 | 检测项②：CLAUDE.md / AGENTS.md / CURRENT.md / README.md 的「当前节点」一致性（正则提取比对） | 不一致即失败 | 已完成（CURRENT.md 为唯一权威声明处；其余文件至多一处且须一致；指针式提及豁免） |
| S2-4 | 检测项③：rules（.claude/rules、未来 .cursor/rules）中引用的 ADR 编号必须存在于 decisions/ 且非空 | 闭环 decisions-traceability | 已完成 |
| S2-5 | 检测项④：CURRENT.md 行数 ≤150（超限提示归档）；project-status.md 只允许追加（本项可先豁免，靠人工纪律） | 超限即警告 | 已完成（超限为 warning 不算失败） |
| S2-6 | 检测项⑤（若采纳 manifest）：docs/ai/manifest 登记项与实际目录双向一致性。**manifest 本身推迟到 S5 之后视需要建立**，避免先造一个靠自觉维护的清单 | 一致性报告 | 暂缓（按计划推迟到 S5 后） |

**退出准则**：check_docs.py 在当前仓库上运行输出全部通过；人为制造一处节点漂移能被它抓到（写进自测）。

---

## S3 CI 流水线 + 分层断言

**目标**：质量门禁从「本地手动」变为「合并自动拦截」；并行开发的前置条件。

| # | 任务 | 内容 | 状态 |
|---|---|---|---|
| S3-1 | GitHub Actions（或等价物）后端 job：`ruff check` → `pytest` 全量 → golden cases（`scripts/run_golden_cases.py`） | .github/workflows/ci.yml | 已完成（ruff 全仓清零后改为全量门禁；mypy 全量因存量债务暂缓，见 ci-troubleshooting.md） |
| S3-2 | admin-web job：`vitest run` → `tsc -b` → `vite build`；frontend job：`tsc --noEmit` | 同上 | 已完成（三件套本地全过 41/41；admin-web 空 lockfile 已重新生成 71KB；补装缺失 peer `@testing-library/dom`） |
| S3-3 | 文档 job：`python scripts/check_docs.py` | 同上 | 已完成（backend job 内 Docs gate 步骤） |
| S3-4 | 分层断言：自研 AST 检查器 `scripts/check_layering.py`（零新依赖，契约测试覆盖）——四条规则 + 组合根豁免名单 | contracts 配置 + CI 集成 | 已完成（8 项契约自测 + 端到端注入违规验证 exit 2） |
| S3-5 | Windows flaky 用例（WinError 10055）标记隔离重试；CI 失败排查指引 | 稳定绿色基线 | 已完成指引（docs/process/ci-troubleshooting.md）；10055 为 Windows 本地特有，CI Linux 不受影响，不阻塞 |
| S3-6 | main 分支保护：必须 CI 全绿才能合并（配合 S6 的合并队列） | 仓库设置 | 未开始（需仓库管理员在 GitHub 设置，代码侧已就绪） |

**退出准则**：一次真实 PR 触发全链路并在约 10 分钟内给出红/绿；故意引入一次分层违规被 S3-4 拦截。

---

## S4 依赖锁定 + 文档对齐实现

**目标**：环境可复现；消灭技术栈虚报。（无前置依赖，可与 S1 并行）

| # | 任务 | 内容 | 状态 |
|---|---|---|---|
| S4-1 | `uv lock`（或 pip-tools）生成 Python 锁文件并提交；OR-Tools / SQLAlchemy / FastAPI 升级政策写入 ADR（升级须带 golden 回归） | lock 文件 + ADR | 已完成（`uv.lock` 141 包提交入库；升级政策 = ADR-0024，含 5 步升级流程与 4 个行为敏感依赖清单；`uv sync` 后全量 pytest 465/465 验证） |
| S4-2 | 统一 Node 引擎约束（frontend `>=22 <23` vs admin-web `>=22 <25`），对齐 package-lock | package.json 修正 | 已完成（统一为 `node >=22 <25` + `npm >=10 <12`；frontend package-lock engines 同步重新生成，diff 仅 4 行；frontend typecheck 过） |
| S4-3 | CLAUDE.md 技术栈表对齐实现（若 S1-3 未覆盖完）：异步任务=自研 holiday-worker、无 COS、LLM 仅 O17 抽取 | 技术栈表修订 | 已完成（AGENTS.md 技术栈表逐行核对：Celery/COS/LLM 虚报 S1 已清除；本项补充 Python 版本口径与 uv.lock 引用；同步脚本重新派生 CLAUDE.md） |

**退出准则**：全新环境按 README + lock 一步装成且 pytest 全绿；技术栈表逐行有代码依据。

---

## S5 脚本契约标准化 + 工具安全分级

**目标**：scripts/ 从「一次性脚本」升级为「跨平台工具面」。

| # | 任务 | 内容 | 状态 |
|---|---|---|---|
| S5-1 | 制定脚本契约并写入 `.claude/rules/`（后派生 Cursor rules）：JSON 输出（`--json`）、稳定退出码（0/1/2）、fail-closed、幂等、写操作必须 `--dry-run` | 契约文档 | 未开始 |
| S5-2 | 工具安全三级分类（成文规则）：只读类→可直接给模型；写入类→dry-run+显式确认；破坏类→永不进模型工具面、一次性用完即删 | rules 条目 | 未开始 |
| S5-3 | 改造首批高价值脚本达标：`report_research_readiness` / `audit_catalog_boundaries`（已是范本，补 --json）/ `run_golden_cases` / `validate_candidate_catalog` / `import_candidate_revisions`（写入类，加 dry-run） | 5 个脚本改造 | 未开始 |
| S5-4 | 每个达标脚本配最小契约测试（退出码 + JSON schema） | tests/scripts/ | 未开始 |
| S5-5 | （按需，暂缓）FastMCP 封装 2–3 个高频脚本供 WorkBuddy 直调；仅当出现真实跨平台直调需求时启动 | — | 暂缓 |

**退出准则**：首批 5 个脚本全部通过契约测试；模型在会话中可直接调用只读类并正确解析 JSON。

---

## S6 并行开发试点

**目标**：验证多会话并行的同步机制，形成可复制的协作规范。

| # | 任务 | 内容 | 状态 |
|---|---|---|---|
| S6-1 | 协作规范写入 AGENTS.md：一会话=一分支=一能力域；文件路径互斥（任务启动时声明触碰清单）；Alembic 迁移号与 `.local/*.db` 共享库互斥（并行期迁移冻结或单会话负责） | 规范条目 | 未开始 |
| S6-2 | CURRENT.md In-flight 区启用：并行任务登记/认领/释放流程 | 登记 | 未开始 |
| S6-3 | 试点任务选择（天然正交）：A=review.py 拆分第一步（只碰 application/admin）、B=敏感词正则修复+单测（只碰正则与 tests）、C=admin 会话持久化（只碰 auth 与前端存储） | 三条分支 | 未开始 |
| S6-4 | 合并队列串行执行：rebase → CI 全绿 → 合并 → 下一个；每次合并后 In-flight 区销账 | 3 次合并 | 未开始 |
| S6-5 | 试点复盘：冲突点、机制缺口写入协作规范 v2 | 复盘记录 | 未开始 |

**退出准则**：3 个任务全部合并且零人工解冲突（或冲突均有机制可防）；协作规范沉淀为正式规则。

---

## S7 上帝类拆分（代码健康切片）

**目标**：消除三大腐化点，为多城市扩展减负。**硬前提：S3 CI 全绿 + R0.2-07 数据批次完成。**

| # | 任务 | 拆分对象 → 目标 | 状态 |
|---|---|---|---|
| S7-1 | `application/admin/review.py`（3443 行）→ 按子域拆为 review_readiness / review_sources / review_geometry / review_relations / publication / retirement；`PlaceReviewWorkflowService` 退化为编排门面；`ReviewRepository` 按子域收窄为多个 Protocol | 6 个模块 | 未开始 |
| S7-2 | `interfaces/http/admin.py`（2011 行）→ 按 O00/O04/O07/O09/O17 路由分文件 + Pydantic 模型归位各路由模块 | 5 个路由模块 | 未开始 |
| S7-3 | `infrastructure/database/place_catalog.py`（1706 行）→ 按聚合根拆仓储 | 3–4 个仓储 | 未开始 |
| S7-4 | `admin-web/src/pages/RevisionDetailsPage.tsx`（1999 行）→ 按证据面板拆组件（来源/几何/访问点/开放时间/关系/发布准备区） | 6+ 组件 | 未开始 |
| S7-5 | `GET /api/v1/trips` N+1 修复：仓储层批量接口（`get_many` / `count_by_trip_ids`） | app.py:461-480 | 未开始 |

**执行纪律**：每个子任务=独立提交；只搬移不改逻辑；每片完成跑全量（pytest 432 + Vitest 41 + typecheck + build + golden）；违反即回滚该片。

**退出准则**：单文件 ≤800 行；全量回归绿；S3-4 分层断言保持通过。

---

## S8 用户端补测 + 契约对照

**目标**：用户触点获得回归保护；契约与实现建立机器对照。

| # | 任务 | 内容 | 状态 |
|---|---|---|---|
| S8-1 | frontend 引入 Vitest，覆盖 `entities/planning`、`features/trip-draft` 的 store 与纯函数（核心路径优先） | 测试集 | 未开始 |
| S8-2 | CI 导出 FastAPI OpenAPI schema 快照，与 `docs/specs/api-contract.md` 关键字段做 diff 校验 | 契约对照 | 未开始 |
| S8-3 | `admin-web/src/api/types.ts` 改为 openapi-typescript 生成，消除手工同步 | 生成式类型 | 未开始 |
| S8-4 | （R0.3 部署后）Playwright E2E 覆盖 H5 核心路径：创建草稿→选点→生成→查看→分享 | E2E 套件 | 未开始 |

**退出准则**：frontend 核心纯函数有测试；OpenAPI diff 纳入 CI；types.ts 由生成产出。

---

## 风险登记与缓解

| 风险 | 影响阶段 | 缓解 |
|---|---|---|
| 文档手术期间多会话同时改 docs/ 造成合并冲突 | S1 | S1 期间文档操作单会话串行完成（半天量级，可接受） |
| 拆分引入行为回归 | S7 | 严格「只搬移不改逻辑」+ 每片全量回归 + 独立提交可回滚 |
| CI 初期 flaky 消磨信任 | S3 | S3-5 先治已知 flaky 再上分支保护 |
| manifest/规范类文档自身漂移 | S2/S5 | 一切新清单必须同时有 check_docs 校验项，否则不建 |
| 改造与 R0.2-05-03 数据主线抢人 | 全局 | S1/S2/S4 属「半天级」可穿插；S7 明确排在数据批次之后 |

## 里程碑

- **M-a（S1+S1.5+S2+S4 完成）**：知识库自维护基线——冷启动 ~3k token，文档漂移有脚本拦截，文档与实现无现存矛盾
- **M-b（S3+S5 完成）**：工程基础设施完备——CI 全绿门槛 + 工具面契约化，**具备并行开发与安全重构前提**
- **M-c（S6 完成）**：并行开发跑通，协作规范 v2 沉淀
- **M-d（S7+S8 完成）**：代码健康达标 + 用户端有回归保护，**具备进入 R0.3 部署与 M2 扩展的基座**

---

*维护约定：每个任务完成时更新对应状态（`未开始→进行中→已完成`），并在 CURRENT.md「最近完成」登记一行；阶段全部完成时更新「阶段总览」表的状态列。本文件由 S2 的 check_docs.py 校验结构有效性。*

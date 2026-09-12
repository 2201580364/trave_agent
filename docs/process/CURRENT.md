# CURRENT — 当前状态滚动快照

> 唯一的「现在」入口。每轮任务结束时更新本文件；历史细节看 [status-archive/](status-archive/)，跨里程碑稳定路线看 [project-roadmap.md](project-roadmap.md)。

- 更新时间：2026-09-12（S7-2 HTTP路由拆分进行中（O05首片完成待提交））
- 当前节点：`M1 后段 / Gate 7 / OM1 / G7-R0.2-05-03 + R0.2-07（多地点审核基线，R0.2-09 O17 已提交）；transformation-plan S8-1/2/3 阶段交付已进入 dev（a657504 / dc5d1ea / 361cc37；响应类型迁移与 S8-4 E2E 未完成），审计规范化 AUD-1～4 已进入 dev（04c2d35），几何证据报错修复已进入 dev（7dda0f7）；S7-1 已启动（用户批准 10 条批次，027/052 已排除；cec78fd 远端全绿由用户确认）`
- 本轮自动验证基线（Python3.12锁定环境、PYTHONUTF8=1）：O05路由/模型专项与管理端HTTP回归通过；ruff、分层139文件零违规、check_docs通过。完整后端/Golden/两端基线沿用上一片，迁移链仍至0015。
- 最近提交基线：`40d4430 refactor(admin): 拆分修订生命周期与证据审核服务`，已进入 dev；本轮完成修订生命周期拆分。

## 最近三轮已完成（一行一项）

- 2026-09-12 S7-1 查询服务（H3，完成待提交）：修订列表/计数、批量读取、准备度摘要、仪表盘、修订详情与证据详情迁至review_queries（约200行），门面1228→约900行；查询Protocol无写入能力。新增4项读取状态不变回归；563/563、Golden8/8、两端回归与门禁通过。S7-1进入门面收口阶段。

- 2026-09-12 S7-1 修订生命周期（H3，已提交40d4430）：创建修订、编辑修订、证据核验迁至review_revision（437行），门面1568→1228行；新增3项事务回滚/重试/重放回归；pytest559/559、Golden8/8、两端回归和门禁通过。修订模块保留18项原有mypy类型债。

- 2026-09-12 S7-1 发布职责（H3，已提交de19da3）：8方法迁至review_publication（640行），门面1996→1568行；PublicationUnitOfWork收窄目录17方法与修订读取接口，AST/签名保持。新增4项审计失败回滚/重试/重放回归，覆盖投影、发布、批次和快照；556/556、Golden8/8、两端回归与门禁通过。发布/修订生命周期收口仍待完成。

- 2026-09-12 批量审核HTTP契约修复（H3，已提交21535b2）：批量项新增必填task_id（1–64字符），单项模型不变；同步API契约与生成类型。原应用层批量回归改为真实HTTP，新增缺失/空/超长ID无审计写入3项。专项9/9、全量552/552、管理端47/47+tsc+build及门禁通过。无研究库/迁移/锁文件改动。

- 2026-09-12 S7-1 审核任务（H3，已提交929d62a）：9方法迁至519行review_tasks，门面2348→1996行；原AST/签名保持，窄化任务仓储和只读证据接口。新增6项事务回滚/重试/重放与批量部分成功测试；549/549、Golden8/8、两端回归及门禁通过。批量HTTP既有输入缺口独立登记，发布/修订生命周期仍待拆分。

- 2026-09-12 S7-1 时间证据（H3/O05，已提交 c4fa989）：时间写入/节假日例外生成迁至 review_time（776行），只读预览迁至 review_time_preview（245行）；时间仓储收窄11方法，门面2954→2348行，原方法AST/签名保持。新增11项事务回滚/重试/重放/intent冲突回归；543/543、Golden8/8、两端验证与门禁通过。未改业务规则、研究库、依赖或迁移；审核任务/发布等继续拆分。

- 2026-09-12 关系裁决成功重放修复（H3，已提交 38d3518）：审计目标仍为relation_id，重放改用已纳入operation_digest的请求revision_id查询；不修改历史审计。扩展既有事务测试：成功重放200且版本/全状态不变；同intent修改decision_note返回409且状态不变。专项2/2、全量532/532（64.16s）、ruff/分层131文件/相关mypy通过。本轮不重复无关前端/Golden，既有基线沿用上一片。

- 2026-09-12 S7-1 关系职责（H3，已提交 b595ecd）：关系裁决/无关系确认迁至200行review_relations，仓储收窄为2方法，证据摘要共享。门面3103→2954行，函数AST/签名/OpenAPI一致。新增2项事务回滚/失败重试回归。532/532（75.02s）、Golden8/8、admin47/47/tsc/build、frontend19/19/tsc、ruff/分层131文件/API/文档与相关模块mypy通过。原有关系裁决成功重放404已用HEAD方法与迁移方法在临时库对照复现，不属于拆分回归，本片保留并登记独立修复。

- 2026-09-12 S7-1 几何/访问点（H3，已进入 dev：e293a56）：6 用例迁入 review_geometry（361 行）；共享证据事务迁入 review_evidence（124 行）供几何与原时间证据复用，GeometryReviewUnitOfWork 收窄为 7 个仓储方法。门面同签名转发，review.py 3362→3103 行。新增6项审计失败回滚/同intent重试/重放回归。后端530/530（111.81s）、Golden8/8、ruff/分层130文件/API及新模块mypy通过；admin47/47/tsc/build、frontend19/19/tsc、文档门禁通过。无迁移/依赖/研究库写入。

- 2026-09-12 S7-1 来源/接口切片（H3，已进入 dev：9cc9792）：5 个来源用例迁至 review_sources（322 行），门面保留同签名转发；review_support（138 行）共享权限/幂等/审计，review_ports（184 行）拆 3 个审核仓储 Protocol 并为来源实际收窄为 2+4 方法接口。累计 review.py 3998→3362 行。新增审计失败回滚与重试/重放两项集成回归；524/524（97.96s）、Golden 8/8、admin47/47/tsc/build、frontend19/19/tsc、ruff/分层128文件/API/文档通过，新模块 mypy 通过。旧门面类型债保留，无迁移/研究库写入。

- 2026-09-12 S7-1 准备度首片（H3，已进入 dev：9cc9792）：evaluate_review_readiness / _readiness_check 原样迁入 243 行 review_readiness.py，原 review.py 3998→3764 行，旧公共导入/私有别名兼容；离线报告直接依赖新模块。新增兼容测试，AST 对比所有原函数/类一致。全量 522/522（96.79s）、专项 14/14、Golden 8/8、admin 47/47/tsc/build、frontend 19/19/tsc、ruff/分层/API/文档全过。首轮 WinError 10055 单项及串行全量复跑通过；无研究库写入。其余职责与 Protocol 尚未拆分，S7-1 未整体完成。

- 2026-09-11 CI 契约测试隔离修复（H3/S8-2，已进入 dev：cec78fd）：测试 fixture 在临时目录真实导出 schema，检查显式传 --schema；当前契约强制 exit 0，缺契约错误隔离验证，只读两次成功且内容不变。专项 7/7、锁定环境全量 521/521（86.72s）、ruff、124 文件分层零违规；文档门禁通过。未改 CI/业务/依赖/研究库，未重跑前端与 Golden，历史基线不冒充本轮结果。用户确认批次排除 027/052，CI 远端已由用户确认全绿。

- 2026-09-11 S4/S8 CI 收尾 + 响应契约首片（H3，已进入 dev：436bf20）：CI 固定 uv 0.8.15，锁定安装 dev extra，全检查使用 --no-sync；frontend 接入 19 项测试并修正 npm ci 的 legacy-peer-deps；后端 OpenAPI artifact 传给管理端，生成类型差异门禁。34 个地点详情/证据/修订写入/审核任务/准备度/时间预览接口明确响应模型，17 个前端类型改生成再导出。保留 null/省略字段/日期字符串；新增 6 项响应契约测试。锁定环境 521/521 + Golden 8/8；管理端 47/47/tsc/build、用户端 19/19/tsc 全过。无锁文件变更、无迁移、未操作研究库。S7 与 S8-4 前提仍未满足。


- 2026-09-11 O05（H3/C2/C4/C6，ADR-0025，已进入 dev：6e9e463）：show 至少一条有效固定场次，已发布投影固化多场次及日期/开放规则/入园截止；单地点单节点、求解器结合 OD 和锚点选择可行场次，完整保留提前入场至演出结束；候选入口常规开放规则/固定场次删除，审核入口仍停用并保留可见，停用证据不参与校验。删除有角色/生命周期/版本/幂等/同事务审计。结果与分享显示真实场次开始，公开分享不暴露场次 ID。无迁移、未操作研究库。验证详情和操作偏差见本月 status-archive。


- 2026-09-08 审计功能规范化 AUD-1～4（评审驱动，已进入 dev：04c2d35）：评审结论=不引入切面/中间件（审计载荷是业务语义、必须与业务同事务，切面形式是伪需求），问题在「对的做法未制度化」——`_event` 构造器三处三样、摘要哈希三处三样、reason_code 校验仅 review 有、动作码零文档。AUD-1 规范 `.claude/rules/audit-logging.md`（核心纪律四条 + 字段语义 + 动作码命名法与逐码登记表 + target_type 表 + digest 唯一实现 + actor_role 双序记账规则 + 新增端点 checklist）；AUD-2/3 共享模块 `application/admin/audit_events.py`（build_audit_event 全关键字构造器 + canonical_digest 唯一实现 + validate_audit_reason + review/identity 双序 role 解析），service/review 的 `_event` 改薄代理、holiday_calendar_sync 5 处裸传 AdminAuditEvent 位置参数全部改写（消灭 17 字段错位风险）；AUD-4 `tests/application/test_audit_registry.py` 3 项——代码发射的动作码必须登记、登记不得超前于代码、target_type 同查，防规范烂尾。行为零变化，pytest/ruff/layering/check_docs 全过。遗留：O17 模块 5 个码历史上是 reason_code 而非 action（已按双射原则在规范中区分登记）。

- 2026-09-08 S8-3 admin-web 生成式 API 类型·小步落地（transformation-plan，实现完成待合并）：openapi-typescript@7 入库（devDep，npmmirror）+ `npm run generate-api-types`，从 `var/reports/openapi-schema.json` 生成 `admin-web/src/api/api-schema.d.ts`（4941 行）；**勘察关键事实：后端 63/73 响应端点声明 `dict[str, object]` 无结构化 schema，生成器只能覆盖请求侧 47 组件**，AdminActor/PlaceRevision 等 20 个响应类型无生成来源暂留手工（后端补 response_model 另立任务，非 S8 范围）；已验证手工输入类型与生成组件双向兼容，`CreateAdminActorInput` 改为 `components['schemas']` 再导出示范（消费方零改动）；types.ts 头部写明过渡期边界与收尾路径；附带修复 vite.config.ts `fileParallelism: 2→false`（vitest 4 类型收窄，数值写法致 tsc -b/build 报 TS2769，S8-2 提交引入、本轮回归暴露）；回归：admin-web vitest 46/46 + tsc + build 全过。

- 2026-09-07 S8-2 OpenAPI 契约对照（transformation-plan，实现完成待合并）：`scripts/export_openapi_schema.py` 离线导出 73 路径完整 schema（内存 SQLite 组合根装配 admin_identity + review_workflow + holiday_calendar_sync，治理 catalog 从 data/governance 加载，不调 bootstrap 无副作用）；`scripts/check_api_contract.py` 解析契约 4 种登记风格做双向 diff（O05 聚合句按 REST 语义展开 POST→集合根、PATCH/DELETE→成员路径；code-only=门禁退出 2，contract-only=信息性；§2.1.1 探针前缀差异按文档化别名处理）；当前 85 契约/82 实现、code_only=0 PASS、contract_only=3（places/{place_id} 计划端点、retry 未排期、trips/generate 旧设计叙述）；发现 2 项契约债：health 探针路径笔误（契约 `/api/v1/health/*` vs 实际 `/health/*`，代码+ops 文档一致）、9 条 O05 时间证据端点以聚合句而非逐条登记（脚本已兼容，建议下版契约改表格）；7 项契约测试 `tests/scripts/test_openapi_contract.py`；全量 pytest、ruff、check_docs、layering 零回退；ci.yml 集成待确认后动冻结文件。
- 2026-09-07 S8-1 frontend Vitest 补测（transformation-plan，实现完成待合并）：vitest@1.6.0 经 `--legacy-peer-deps` 安装（Taro 4.2.1 的 `peerOptional vite@^4` 与 vitest 携带依赖的 vite@5 peer 冲突；Taro 构建实际走 webpack5，vite 仅服务 vitest 运行）；`frontend/vitest.config.ts`（`@` 别名对齐 tsconfig paths、node 环境、默认 include `*.test.ts(x)`）；`npm run test` script；19 项测试全过——store 13 项（会话/草稿生命周期/行程与 Revision 导航/replacePlan 语义/persist 经 Taro storage 序列化与 reset 清空）+ api client 6 项（成功透传、Bearer 头、网络失败→status 0 network_unavailable、HTTP 错误信封→code/details 映射、无信封回退 request_failed）；tsc --noEmit 零错误；CI 集成留给 S8-2 统一处理。另：账本收口——transformation-plan V1.1（S5/S6/S3-6 状态对齐 git 实际、里程碑 M-a/M-b/M-c 达成标记）+ parallel-workflow v2.1 第八节账本时效纪律（单会话同样适用，收尾三件事）。
- 2026-09-07 S6 并行开发试点（transformation-plan，已合并 `fae014e`）：协作规范落地 `.claude/rules/parallel-workflow.md` 并经复盘升版 v2（一会话=一分支=一能力域 + In-flight 登记 + 迁移/共享库互斥 + 合并队列纪律 + 基线口径/验证纪律）；AGENTS.md 加 2 行硬规则；试点任务 C=admin 会话持久化（sessionStorage + 挂载 /me 恢复）；全量回归零回退。

- 2026-09-07 S5 脚本契约标准化 + 工具安全分级（transformation-plan）：`.claude/rules/script-contract.md`（契约七条 + L1/L2/L3 三级分类 + scripts/ 全量 26 脚本分级登记）；首批 5 脚本达标改造（report_research_readiness 补 --json、audit_catalog_boundaries 补缺库 fail-closed 退出 1、validate_candidate_catalog 0/1/2 语义 + 修复 SourceRegistryError 未捕获崩溃、run_golden_cases 补 --json + 门禁失败 1→2、import_candidate_revisions 补 --json + 修复空库 dry-run 崩溃）；`tests/scripts/test_script_contracts.py` 10 项契约测试全过；同步更新存量断言（status "valid"→"ok"）。
- 2026-09-05 api-contract V2.11 端点差异裁决落地（S1.5-1 ②收尾，本会话）：6 条全部裁决——删除 `POST /admin/candidates`（与 `POST /places/{place_id}/revisions` 重复）；删除独立 `POST /admin/places/{place_id}/retirements`，§15.2 新增「发布版本退役语义」声明（退役由 publications 单条/批次链路发布新版时同事务原子完成，不提供绕过发布门禁的退役通道）；`GET /admin/places/{place_id}` 移入新增 §15.2.0「计划端点」小节；补登 3 个已实现端点（`GET /place-revisions/{revision_id}`、`GET /dashboard-summary`、`GET /holiday-calendar-sync-capability`）；retry（P1）标注未排期；health 探针写入 §2.1.1 运维探针。check_docs 全过。
- 2026-09-05 S4 依赖锁定 + 文档对齐实现（transformation-plan）：`uv.lock`（141 包）入库，`uv sync` 后全量 pytest 465/465 验证；升级政策 ADR-0024（5 步升级流程 + 4 个行为敏感依赖 ortools/sqlalchemy/alembic/fastapi 清单，golden 差异即停）；frontend/admin-web Node engines 统一为 `>=22 <25`、npm `>=10 <12`（frontend package-lock engines 同步再生，diff 仅 4 行，typecheck 过）；AGENTS.md 技术栈表核对实现（Celery/COS/LLM 虚报 S1 已清，本项补 Python 版本口径与 uv.lock 引用），sync 脚本重派生 CLAUDE.md。
- 2026-09-05 S3 CI 流水线 + 分层断言（transformation-plan）：`.github/workflows/ci.yml` 三 job（backend: ruff+pytest+golden+layering+docs；admin-web: vitest+tsc+build；frontend: tsc）；自研 `scripts/check_layering.py` 四规则 + 组合根豁免 + 8 项契约自测；ruff 存量 170→0（formatter 批量清偿，全量 pytest 465/465 验证零语义破坏）；修复 P0-1 乱码正则（中文敏感词「私钥/密码/令牌」恢复拦截 + 17 项回归测试）；CI 排查指引 `docs/process/ci-troubleshooting.md`。
- 2026-09-04 版本退役语义修复（R0.2-07）：发布新版本时原子退役同一地点旧 `published` Revision/Projection（转 `retired`、`solver_eligible=false`），历史保留但不再进入用户端求解目录；已修复 research.db 浙江省博物馆孤山馆区旧第 1 版；新增持久化回归。
- 2026-09-03 O17 可执行同步闭环提交（`c2ea117`）：中国政府网公告发现器、受限域名获取器、供应商中立 OpenAI-compatible 抽取适配器、独立 `travel-agent-holiday-worker` 进程（有限批次/周期轮询/优雅停止/lease 恢复/同年度运行锁/指数退避）；管理页面含任务详情、预览数据确认弹窗、取消端点与 AI/系统执行过程时间线；真实 2024 年同步已完成人工验收；迁移 0014/0015。
- 2026-09-03 多地点审核基线（G7-R0.2-05-03/R0.2-07）：`report_research_readiness.py` 只读工具；修复两个批量审核前门禁缺口（编辑基础事实/新增证据清除导入期核验标记；Revision 审核通过要求六项准备度全部采集且核验）；研究库母集 72 条（published=3、candidate=69）；选定下一轮 12 条人工审核批次（`hz-cand-003/006/010/013/014/020/024/027/042/045/048/052`）。

## 下一步（按顺序）

1. 继续 S7-1：继续S7-2：拆分O05路由注册，再按O04/O07-O09/O17分片；S7-1业务职责已拆出，门面显式兼容转发约1027行；准备度/来源/几何/关系/时间职责已拆出；本地原批次剩余 027/052 两条 candidate，048 已发布场次的最晚入场晚于开始 10 分钟，需按 ADR-0025 核对。
2. 稳定后扩展研究目录至 50–75 条 `human_verified`（G7-R1 研究最低目录门槛）。
3. 实施 R0.2-06 按需真实 OD 子图（候选过滤→锚点真实 OD→缓存→不可变子图 hash→Revision 回放，缺边不填 0）。
4. 进入 R0.3 服务器全栈 Compose/HTTPS/环境锁定；期间 G1 真实用户发现研究补证可与 R0.2–R0.4 并行、R1 前关闭。

## 本地运行验证（2026-09-11）

- 用户要求启动全部本地服务后，已启动 API 8000/8001、管理端 5173、H5 10086、O17 worker；页面及两端代理 `/health/ready` 均 200，两个 API 的 OpenAPI 均含本轮 PlaceRevision 响应模型，H5 编译成功、worker 启动日志确认。
- 沿用 `.env` 的研究 SQLite，启动前只读确认迁移为 0015，正常应用初始化/worker 队列运行已获本轮启动指令授权；未启动 MySQL/Redis。日志在 `var/reports/services-20260911-170900/` 及 `logs/`。这是本地运行冒烟，不代表完整用户验收或远端 CI 通过。

## 活跃风险

- 批量审核HTTP任务ID缺口已独立修复待提交：专用批量项要求task_id，真实HTTP回归覆盖部分成功/重试；单项输入保持。
- 审核任务模块保留从旧门面迁入的4项mypy类型债（准备度dict迭代、批量int转换/reason_text），原门面18项已迁入修订模块；不声明mypy整体通过。

- S7-1 关系切片发现原有重放缺陷：resolve_relation 的审计 target_id 是 relation_id，但成功重放用它查询 revision，通常返回404。HEAD e293a56 同样存在；本轮已改用digest绑定的请求revision_id查询，成功重放及不同载荷intent冲突回归通过，修复已提交 38d3518。来源/无关系确认重放与此不同。

- CI 配置已改为 `uv sync --locked --extra dev` + `uv run --no-sync`，frontend 增加 Vitest；admin-web 下载 backend schema 并检查生成类型差异。原 job check 名称保留。历史缺快照失败已由 cec78fd 修复，用户确认三项远端检查全绿。


- O05 显式场次日期暂不执行 DAY_SPREAD/普通景点时长扩展，保留最低游览时长和晚餐软块；无显式场次的日期保持原算法。已实现/自动测试通过不等于已部署或用户验收。
- 上轮非锁定环境缺口已补：本轮新建 `var/venvs/ci-locked-20260911`，以 uv 0.8.15 按 lock 安装，515 原基线和新增响应契约回归全过。默认 python 仍为 Conda，后续使用明确 uv 环境；Windows 子进程设置 PYTHONUTF8=1。


- 2026-09-10 提交核对：S6 已实现 sessionStorage + /me 会话恢复，但 ADR-0020 仍禁止持久化且要求新 ADR，当前未见替代决策；最新几何修复在组件中展示客户端校验文案，与 error-messages.md 的全局单一文案源要求存在边界差异。后续相关实现前须先裁决，不能把现有代码自动当作规格变更。
- 2026-09-11 只读核对：原 12 条批次 10 published / 2 candidate（杭州博物馆 027、良渚博物院 052，均无更新版本）；钱江新城灯光秀 048 的 4 条有效固定场次 entry=start+10，不满足当前 valid_session_timing，因此准备度为 5/6。用户已明确排除 027/052，批准批次为其余 10 条；048 时间证据差异单独保留，不自动修改或豁免。

- Gate 1 存在真实用户研究补证债务：无真实访谈纪要与可追溯结论，M1 最终决策前必须完成 8–10 名目标用户发现研究，不得倒填。
- 历史账本记载的测试计数互相矛盾（352/363/367/370/…/432），以本文件顶部稳定测试基线为准；旧计数属阶段性快照，不代表回退。
- 全仓 strict mypy 存量类型债（数百条/数十文件，mypy 2.3 比建仓时代更严格），未纳入本轮范围；CI 暂不跑 mypy 全量（见 docs/process/ci-troubleshooting.md 已知债务节）；ruff check 债务已清零（2026-09-05），`ruff format` 历史漂移 103 文件为 non-blocking。
- 服务器真实 MySQL 仍停在已验收的 `0002_anonymous_identity` 基线，下次应用发布前必须依次执行 0003→0015 并重新验证 readiness、备份与隔离恢复。
- H1–H12 全部「未验证」；自动化测试、Chrome 验收或团队内部判断均不能冒充 H3/H11 的真实用户证据。
- Windows 偶发 `WinError 10055` 套接字错误为环境 flaky（隔离复跑即过），非业务回归。

## In-flight 区（并行任务登记）

| 任务 | 分支 | 触碰文件 | 状态 |
|---|---|---|---|
| 关系裁决重放修复（H3） | dev | `application/admin/review_relations.py`、`tests/application/test_review_relation_boundary.py`、CURRENT/改造计划/本月归档 | 已提交 38d3518；专项2/2、后端532/532、ruff/分层/mypy通过 |
| S7-2 O05路由拆分（H3） | dev | `interfaces/http/{admin,admin_o05,admin_time_models}.py`、CURRENT/改造计划/本月归档 | 完成待提交；现有管理端HTTP回归、ruff、分层139文件、文档门禁通过 |
| S7-2 O05请求模型归位（H3） | dev | `interfaces/http/{admin,admin_time_models}.py`、CURRENT/改造计划/本月归档 | 完成待提交；563/563、门禁通过 |
| S7-1 查询服务（H3） | dev | `application/admin/{review,review_queries,review_ports}.py`、`tests/application/test_review_query_boundary.py`、CURRENT/改造计划/本月归档 | 完成待提交；563/563、Golden8/8、两端验证通过 |
| S7-1 修订生命周期（H3） | dev | `application/admin/{review,review_revision,review_ports}.py`、`tests/application/test_review_revision_boundary.py`、CURRENT/改造计划/本月归档 | 进行中 |
| S7-1 发布服务（H3） | dev | `application/admin/{review,review_publication,review_ports}.py`、`tests/application/test_review_publication_boundary.py`、CURRENT/改造计划/本月归档 | 已提交de19da3；556/556、Golden8/8、两端验证通过 |
| 批量审核HTTP契约修复（H3） | dev | `interfaces/http/admin.py`、`tests/application/test_review_task_boundary.py`、`admin-web/src/api/api-schema.d.ts`、`docs/specs/api-contract.md`、CURRENT/改造计划/本月归档 | 已提交21535b2；552/552、管理端验证通过 |
| S7-1 审核任务（H3） | dev | `application/admin/{review,review_ports,review_tasks}.py`、`tests/application/test_review_task_boundary.py`、`docs/process/{CURRENT,transformation-plan}.md`、本月归档 | 已提交929d62a；549/549、Golden8/8、两端验证通过 |
| S7-1 时间证据（H3） | dev | `application/admin/{review,review_ports,review_time,review_time_preview}.py`、`tests/application/test_review_time_boundary.py`、`docs/process/{CURRENT,transformation-plan}.md`、本月归档 | 已提交 c4fa989；543/543、Golden8/8、两端验证与门禁通过 |
| S7-1 关系裁决（H3） | dev | `application/admin/{review,review_ports,review_evidence,review_relations}.py`、`tests/application/test_review_relation_boundary.py`、`docs/process/{CURRENT,transformation-plan}.md`、本月归档 | 已提交 b595ecd；532/532、Golden8/8、两端验证通过；已有关系重放缺陷单独登记 |
| S7-1 几何/访问点与证据事务（H3） | dev | `application/admin/{review,review_ports,review_geometry,review_evidence}.py`、`tests/application/test_review_geometry_boundary.py`、`docs/process/{CURRENT,transformation-plan}.md`、本月归档 | 已进入 dev（e293a56）；530/530、Golden8/8、两端验证通过，S7-1仍进行中 |
| S7-1 准备度职责迁移（H3） | dev | `application/admin/{review,review_readiness,review_ports,review_support,review_sources}.py`、`data_governance/research_readiness.py`、`tests/application/{test_admin_review_readiness,test_review_source_boundary}.py`、`docs/process/{CURRENT,transformation-plan}.md`、本月归档 | 已进入 dev（9cc9792）；524/524、Golden 8/8、admin47/47/tsc/build、frontend19/19/tsc；新模块 mypy 通过，S7-1 其余子域待拆分 |
| CI 契约测试隔离修复（H3/S8-2） | dev | `tests/scripts/test_openapi_contract.py`、`docs/process/{CURRENT,transformation-plan,ci-troubleshooting}.md`、本月归档 | 已进入 dev（cec78fd）；用户确认远端全绿 |
| S7 前置核对与拆分准备（H3） | dev | `docs/process/{CURRENT,transformation-plan}.md`、`docs/process/status-archive/2026-09.md` | 前置核对完成；批次排除 027/052、用户确认 CI 全绿，S7-1 已启动 |
| S4/S8 CI 收尾与响应契约首片（H3 / transformation-plan） | dev | `.github/workflows/ci.yml`、`docs/process/{CURRENT,transformation-plan,ci-troubleshooting}.md`、本月归档；`interfaces/http/{admin,admin_responses}.py`、`admin-web/src/api/{adminApi,types}.ts`、`api-schema.d.ts`、相关页面测试、`tests/application/test_admin_response_contract.py`、API 规格 | 已进入 dev（436bf20）；521/521 + Golden 8/8，两端验证通过；后续 cec78fd 修复后远端全绿（用户确认） |
| O05 多场次与候选时间规则删除（H3/C2） | dev | `application/admin/review.py`、`domain/place_catalog/{projection,repositories}.py`、`infrastructure/database/place_catalog.py`、`interfaces/http/admin.py`、`admin-web/src/{api,pages}` 相关文件及测试、API/领域规格、ADR、审计规则 | 已进入 dev（6e9e463，本轮核对销账）；另含 solver、infrastructure/solver、frontend 行程展示、sharing、快照脚本、生成 API 类型和对应测试；未操作实际研究库 |
| AUD 审计规范化 | dev（同会话接续 S8-3） | `.claude/rules/audit-logging.md`（新增规范）、`src/travel_agent/application/admin/audit_events.py`（新增共享模块）、`service.py`/`review.py`/`holiday_calendar_sync.py`（构造器/摘要/校验收敛）、`tests/application/test_audit_registry.py`（新增 3 项）、`docs/process/CURRENT.md` | 已进入 dev（04c2d35；2026-09-10 核对销账；原验证记录：pytest 495/495 + ruff + layering + check_docs） |

> S1–S6 全部完成并已合并销账（S5=`941578e`、S6=`fae014e`）；S8-1/2/3 阶段交付已进入 dev（S8-1=`a657504`、S8-2=`dc5d1ea`、S8-3=`361cc37`）；S8-4 等 R0.3，响应类型仍待迁移，frontend Vitest CI 配置已进入 dev（436bf20）；S7 用户已确认批准其余 10 条，排除 027/052；cec78fd 远端全绿已由用户确认，S7-1 已启动。遗留任务：① 响应模型首片 34 个接口已进入 dev（436bf20），其余认证/来源冲突/批量审核/发布批次/O17 等按能力片迁移（原 63 为旧勘察计数，不作剩余数量）；② O17 模块 5 个 reason_code 与 action 命名法的历史混用已登记规范，重构顺延到下次触碰 holiday_calendar_sync 时处理。

## 关键事实速查

- 研究库 `.local/research.db`：2026-09-11 mode=ro 查询全部 Revision 为 published=13、candidate=59、retired=2（版本数量，非全量 Place 去重统计）；原批次 12 条中 10 published、2 candidate。
- 求解器契约：`solver-p1-v2 / trip-result-v2 / constraints-p1-v6 / parameters-p1-2026-08-26`；历史 Revision 不迁移、不覆盖、不原地重算。
- Gate 7 protocol 规范化 SHA-256：`b791f0558dfc93af4cc919ec6dd9b09d1251f8f1d54b7bc0bb8809eade742d89`。
- 正式发布 bundle：`var/published/hangzhou-published-2026-08-27-v1.json`（7 景点 human_verified 坐标 + 42/42 高德 OD + 真实和风三日天气）。
- 本机禁止部署/启动 MySQL/Redis；本地开发组合根用明确标注的近似 fixture，生产组合根只加载严格验证的 published 快照。

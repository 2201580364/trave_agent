# CURRENT — 当前状态滚动快照

> 唯一的「现在」入口。每轮任务结束时更新本文件；历史细节看 [status-archive/](status-archive/)，跨里程碑稳定路线看 [project-roadmap.md](project-roadmap.md)。

- 更新时间：2026-09-16（十景点整段行程质量修复与内置Chrome复测）
- 当前节点：`M1 后段 / Gate 7 / OM1；发布目录动态数据库接入已部署；用户端按请求读取最新 published Projection，无需重启；关系裁决形成的互斥组进入选点与求解约束；OD近邻分天保护已修复并完成7景点回归；游客规划→选点→求解→行程详情已本地与线上验收`
- 线上验收：API 使用 `api-20260915-ui11`，用户端使用 `user-h5-20260915-ui11`；修复 MySQL `INT` random_seed 溢出、静态资源缓存后，杭州 3 日行程生成成功，质量门禁通过，0 条未排入；用户端首页已显示“登录 / 注册”，用户端与管理端自有容器均保持运行。
- 本轮自动验证基线（Python3.12锁定环境、PYTHONUTF8=1）：后端582/582（120.10秒）、Golden8/8、ruff（src/tests/scripts）、153文件分层、新质量四模块定向mypy、sync/check_docs通过。无新增迁移。
- 本轮本地真实浏览器验收：复用内置Chrome，09-30至10-02、09:00开始/18:00末日结束、指定10景点选择→生成→三天逐页检查→刷新恢复，10已安排/0未排入。H5已实际编译，本轮未重复无改动前端的typecheck/vitest。
- 已有关系约束基线：已发布且 `human_verified` 的 `selection_exclusion_groups` 随数据库目录加载到 `PublishedAttraction`；选点接口与 `ProductionSolverGateway` 双层拒绝同组重复选择，已有数据库/求解器回归随本轮全量通过。
- 最近提交基线：HEAD `731da1b`（OD强近邻分天）；本轮 ADR-0027 十景点质量修复为未提交工作区改动，提交由用户手动执行。

## 最近三轮已完成

- 2026-09-16 十景点质量（H3，ADR-0027，完成待提交）：恢复跨日可行性后重平衡实际负载；固定场次日执行完整用餐/普通建议时长/下午展开；真实航次保留星期和有效日期，撤销错误合窗。后端582/582、Golden8/8、ruff/分层153文件/新质量四模块mypy通过。内置Chrome实际10安排/0未排入、逐日及刷新验证通过。详见 [质量报告](../test/reports/solver-quality-20260916.md)。已本地部署，未线上部署，待用户复测。
- 2026-09-16 七景点近邻（已提交731da1b）：OD强近邻在分天再平衡时保留；7点浏览器生成和两组近邻同日验证完成，历史细节见本月归档。
- 2026-09-15 管理端与用户端流程：三地点两轮审核发布、晚入场规则、分享展示及用户端规划验收完成；历史版本与提交证据见本月归档。

## 下一步（按顺序）

1. 完成 G7-R0.2-05-03 / R0.2-07：对已选定的 12 条代表性候选完成六项审核准备度、Projection、批次发布与用户端可见性回归。
2. 扩展研究目录至 50–75 条 `human_verified` Place，达到 G7-R1 研究最低目录门槛。
3. 实施 R0.2-06 按需真实有向 OD 子图：候选过滤、真实 OD 获取、缓存、不可变子图 hash、Revision 回放，缺边不填 0。
4. 进入 R0.3 服务器全栈 Compose/HTTPS/环境锁定；G1 真实用户发现研究可并行准备，并在 R1 外部招募前关闭。

本轮完成 R0.2-06 求解接入与回放快照，专项子图/求解器回归 13/13 通过；新增 R0.3 首片 `api.Dockerfile`、`web.Dockerfile`、`admin-web.Dockerfile`、`Caddyfile`，并将 Compose 扩展为 api/user-h5/admin-web/edge 与 MySQL/Redis 同一项目。Docker 未安装于本机，Compose 构建/健康检查待服务器执行。

## 本地运行验证（2026-09-16）

- API8000/8001、管理端5173、H5 10086已启动本轮代码。浏览器新Revision `revision_08236f82bc344634b3664601666edcc0`，日期09-30至10-02；10安排/0未排入，三日负载334/488/356分钟，每天午餐60/晚餐90。以下早期基线仅保留运维背景。

- 用户要求启动全部本地服务后，已启动 API 8000/8001、管理端 5173、H5 10086、O17 worker；页面及两端代理 `/health/ready` 均 200，两个 API 的 OpenAPI 均含本轮 PlaceRevision 响应模型，H5 编译成功、worker 启动日志确认。
- 沿用 `.env` 的研究 SQLite，启动前只读确认迁移为 0015，正常应用初始化/worker 队列运行已获本轮启动指令授权；未启动 MySQL/Redis。日志在 `var/reports/services-20260911-170900/` 及 `logs/`。这是本地运行冒烟，不代表完整用户验收或远端 CI 通过。

## 活跃风险

- `SOLVER-DAY-001` 已解决：Step 1 的 OD 聚类时长平衡曾拆散发布 OD 中的强近邻；现保留对称 OD ≤10 分钟的近邻对，新增杭州七景点回归。浏览器本轮已重启服务并完成十景点三日页面复测。
- `SOLVER-DAY-002` 已解决并更正方案：数据库适配保留营业星期/季节，只把opening_hours作为普通时间窗；非show航次也加载真实离散场次。撤销上一轮合窗，实际冲突继续阻断。
- `DATA-PLACE-001` 已由用户发布修订解决：2026-09-16当前断桥建议70分钟，灵隐寺150分钟；本轮未修改地点数据。

- 批量审核HTTP任务ID缺口已独立修复待提交：专用批量项要求task_id，真实HTTP回归覆盖部分成功/重试；单项输入保持。
- 审核任务模块保留从旧门面迁入的4项mypy类型债（准备度dict迭代、批量int转换/reason_text），原门面18项已迁入修订模块；不声明mypy整体通过。

- S7-1 关系切片发现原有重放缺陷：resolve_relation 的审计 target_id 是 relation_id，但成功重放用它查询 revision，通常返回404。HEAD e293a56 同样存在；本轮已改用digest绑定的请求revision_id查询，成功重放及不同载荷intent冲突回归通过，修复已提交 38d3518。来源/无关系确认重放与此不同。

- CI 配置已改为 `uv sync --locked --extra dev` + `uv run --no-sync`，frontend 增加 Vitest；admin-web 下载 backend schema 并检查生成类型差异。原 job check 名称保留。历史缺快照失败已由 cec78fd 修复，用户确认三项远端检查全绿。


- O05显式场次日跳过精修的问题已由ADR-0027解决；质量策略是有预算局部搜索，不承诺全局最优。本地近似OD仍可能低估步行，博物馆室外标记需核验，已登记OD-QUALITY-001/DATA-PLACE-002。
- 上轮非锁定环境缺口已补：本轮新建 `var/venvs/ci-locked-20260911`，以 uv 0.8.15 按 lock 安装，515 原基线和新增响应契约回归全过。默认 python 仍为 Conda，后续使用明确 uv 环境；Windows 子进程设置 PYTHONUTF8=1。


- 2026-09-10 提交核对：S6 已实现 sessionStorage + /me 会话恢复，但 ADR-0020 仍禁止持久化且要求新 ADR，当前未见替代决策；最新几何修复在组件中展示客户端校验文案，与 error-messages.md 的全局单一文案源要求存在边界差异。后续相关实现前须先裁决，不能把现有代码自动当作规格变更。
- 2026-09-15 业务流程验收与问题收口：三地点两轮候选→审核→投影→发布已完成；用户端3安排/0未排入，喷泉显示18:40入场·18:30场次。管理端固定场次提示和分享卡晚入场展示已修复并通过回归；平湖秋月仍等待真实来源补齐基础事实，严格mypy存量债务继续单独治理。详情见 `docs/test/reports/admin-lifecycle-review-20260915.md` 与 `var/reports/admin-issue-ledger-20260915.json`。
- 2026-09-11 只读核对：原 12 条批次 10 published / 2 candidate（杭州博物馆 027、良渚博物院 052，均无更新版本）；钱江新城灯光秀 048 的时间证据差异单独保留，不自动修改或豁免。

- Gate 1 存在真实用户研究补证债务：无真实访谈纪要与可追溯结论，M1 最终决策前必须完成 8–10 名目标用户发现研究，不得倒填。
- 历史账本记载的测试计数互相矛盾（352/363/367/370/…/432），以本文件顶部稳定测试基线为准；旧计数属阶段性快照，不代表回退。
- 全仓 strict mypy 存量类型债（数百条/数十文件，mypy 2.3 比建仓时代更严格），未纳入本轮范围；CI 暂不跑 mypy 全量（见 docs/process/ci-troubleshooting.md 已知债务节）；ruff check 债务已清零（2026-09-05），`ruff format` 历史漂移 103 文件为 non-blocking。
- 服务器真实 MySQL 已通过 readiness 核对至 `0016_expand_alembic_version`；后续迁移或部署仍需保留 readiness、备份与隔离恢复核对。
- H1–H12 全部「未验证」；自动化测试、Chrome 验收或团队内部判断均不能冒充 H3/H11 的真实用户证据。
- Windows 偶发 `WinError 10055` 套接字错误为环境 flaky（隔离复跑即过），非业务回归。

## In-flight 区（并行任务登记）

| 任务 | 分支 | 触碰文件 | 状态 |
|---|---|---|---|
| 十景点整体排程质量（H3/C2/C4/C6） | dev | `solver/{schedule_refinement,quality_refinement,quality_policy,segments,time_windows,contract}.py`、`infrastructure/solver/{gateway,database_published,schedule_quality}.py`、相关tests、ADR-0027、solver规格、CURRENT/改造计划/本月归档、质量报告；研究库仅页面新建行程 | 已完成本地工程验收，待用户手动提交及人工复测，未线上部署 |
| 固定场次允许开场后入场及三地点生命周期验收（H3/C2，2026-09-15） | dev | `domain/place_catalog/session_payload.py`、`solver/{models,time_windows,routing,day_assignment,contract}.py`、`infrastructure/solver/database_published.py`、相关 tests、ADR/规格、CURRENT、本月归档、验收报告；本地 research.db 经业务接口写入 | 已完成验收；实现与文档待用户手动提交；账本剩余2项：平湖秋月真实事实补证、全仓mypy存量债 |
| S7-4 O04完整组件迁移（H3） | dev | `admin-web/src/pages/{GeometryAccessEvidenceCard,RevisionDetailsPage,revisionDetailFields}.tsx`、`revisionDetailDisplay.ts`、CURRENT/改造计划/本月归档 | 实现完成待提交；47/47、typecheck、build通过 |
| S7-4 来源证据组件（H3） | dev | `admin-web/src/pages/{RevisionDetailsPage,SourceEvidenceCard,revisionDetailFields}.tsx`、`revisionDetailDisplay.ts`、CURRENT/改造计划/本月归档 | 进行中 |
| S7-3 仓储职责拆分（H3，已提交 bca173f）；S7-4 管理端详情页拆分进行中（O04 几何/访问点完整组件迁移已提交；O05 时间证据完整组件迁移已提交；O07 关系证据完整组件迁移已提交；O06 来源冲突与验证汇总组件已提交；发布阻断计算组件已提交；修订操作区组件已提交；发布准备组件完成待提交） | dev | `infrastructure/database/{place_catalog,place_catalog_reads,place_catalog_ports}.py`、CURRENT/改造计划/本月归档 | 进行中 |
| 关系裁决重放修复（H3） | dev | `application/admin/review_relations.py`、`tests/application/test_review_relation_boundary.py`、CURRENT/改造计划/本月归档 | 已提交 38d3518；专项2/2、后端532/532、ruff/分层/mypy通过 |
| S7-2 O09路由拆分（H3） | dev | `interfaces/http/{admin,admin_o09}.py`、CURRENT/改造计划/本月归档 | 完成待提交；管理端HTTP回归、ruff、分层通过 |
| S7-2 O07/O08路由拆分（H3） | dev | `interfaces/http/{admin,admin_o07_o08}.py`、CURRENT/改造计划/本月归档 | 完成待提交；管理端HTTP回归、ruff、分层141文件、文档门禁通过 |
| S7-2 O04路由拆分（H3） | dev | `interfaces/http/{admin,admin_o04}.py`、CURRENT/改造计划/本月归档 | 完成待提交；管理端HTTP回归、ruff、分层通过 |
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
| O05 多场次与候选时间规则删除（H3/C2） | dev | `application/admin/review.py`、`domain/place_catalog/{projection,repositories}.py`、`infrastructure/database/place_catalog.py`、`interfaces/http/admin.py`、`admin-web/src/{api,pages}` 相关文件及测试、API/领域规格、ADR、审计规则 | 已进入 dev（6e9e463，本轮核对销账）；另含 solver、infrastructure/solver、frontend 行程展示、sharing、快照脚本、生成 API 类型和对应测试；本轮已按 ADR-0026 完成晚入场规则实现与三地点实际生命周期验收 |
| AUD 审计规范化 | dev（同会话接续 S8-3） | `.claude/rules/audit-logging.md`（新增规范）、`src/travel_agent/application/admin/audit_events.py`（新增共享模块）、`service.py`/`review.py`/`holiday_calendar_sync.py`（构造器/摘要/校验收敛）、`tests/application/test_audit_registry.py`（新增 3 项）、`docs/process/CURRENT.md` | 已进入 dev（04c2d35；2026-09-10 核对销账；原验证记录：pytest 495/495 + ruff + layering + check_docs） |

> S1–S6 全部完成并已合并销账（S5=`941578e`、S6=`fae014e`）；S8-1/2/3 阶段交付已进入 dev（S8-1=`a657504`、S8-2=`dc5d1ea`、S8-3=`361cc37`）；S8-4 等 R0.3，响应类型仍待迁移，frontend Vitest CI 配置已进入 dev（436bf20）；S7 用户已确认批准其余 10 条，排除 027/052；cec78fd 远端全绿已由用户确认，S7-1 已启动。遗留任务：① 响应模型首片 34 个接口已进入 dev（436bf20），其余认证/来源冲突/批量审核/发布批次/O17 等按能力片迁移（原 63 为旧勘察计数，不作剩余数量）；② O17 模块 5 个 reason_code 与 action 命名法的历史混用已登记规范，重构顺延到下次触碰 holiday_calendar_sync 时处理。

## 关键事实速查

- 研究库 `.local/research.db`：2026-09-11 mode=ro 查询全部 Revision 为 published=13、candidate=59、retired=2（版本数量，非全量 Place 去重统计）；原批次 12 条中 10 published、2 candidate。
- 求解器契约：`solver-p1-v2 / trip-result-v2 / constraints-p1-v8 / parameters-p1-2026-09-16`；历史 Revision 不迁移、不覆盖、不原地重算。
- Gate 7 protocol 规范化 SHA-256：`b791f0558dfc93af4cc919ec6dd9b09d1251f8f1d54b7bc0bb8809eade742d89`。
- 正式发布 bundle：`var/published/hangzhou-published-2026-08-27-v1.json`（7 景点 human_verified 坐标 + 42/42 高德 OD + 真实和风三日天气）。
- 本机禁止部署/启动 MySQL/Redis；本地开发组合根用明确标注的近似 fixture，生产组合根只加载严格验证的 published 快照。

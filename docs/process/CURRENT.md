# CURRENT — 当前状态滚动快照

> 唯一的「现在」入口。每轮任务结束时更新本文件；历史细节看 [status-archive/](status-archive/)，跨里程碑稳定路线看 [project-roadmap.md](project-roadmap.md)。

- 更新时间：2026-09-16（邻近质量修复、问题清单收口与内置Chrome页签复测）
- 当前节点：`M1 后段 / Gate 7 / OM1；发布目录动态数据库接入已部署；用户端按请求读取最新 published Projection；关系裁决形成的互斥组进入选点与求解约束；OD近邻分天保护与十景点整段质量修复已提交；问题清单剩余项已收口`
- 线上验收：API 使用 `api-20260915-ui11`，用户端使用 `user-h5-20260915-ui11`；修复 MySQL `INT` random_seed 溢出、静态资源缓存后，杭州 3 日行程生成成功，质量门禁通过，0 条未排入；用户端首页已显示“登录 / 注册”，用户端与管理端自有容器均保持运行。
- 本轮自动验证基线（Python3.12锁定环境、PYTHONUTF8=1）：后端全量 pytest 通过（本轮代码修复后）；Golden9/9；ruff（src/tests/scripts）、全仓mypy 242文件、153文件分层、check_docs通过。新增投影/O17/OD定向回归通过。无新增迁移。
- 本轮本地服务复测：API8000、管理端5173、用户端H5 10086已恢复；内置Chrome新开用户端页签完成“什么时候去”→“想去哪里”→“确认并生成”，页面边界为09-30至10-02、09:00开始、18:00结束。页面真实显示3天、10已安排/0未排入；切换三天并刷新后仍能恢复同一行程。
- 已有关系约束基线：已发布且 `human_verified` 的 `selection_exclusion_groups` 随数据库目录加载到 `PublishedAttraction`；选点接口与 `ProductionSolverGateway` 双层拒绝同组重复选择，已有数据库/求解器回归随本轮全量通过。
- 最近提交基线：HEAD `99e5ac4`（十景点整段质量修复已由用户提交）；本轮问题清单收口为未提交工作区改动，提交由用户手动执行。

## 最近三轮已完成

- 2026-09-16 问题清单收口（H3，完成待提交）：TYPE-001/OD-QUALITY-001/ADMIN-DATA-001/DATA-PLACE-002关闭；新增修复O17权限500、投影data_verified持久化、关系来源父子端点门禁不一致。平湖秋月v4通过应用接口发布，data_verified=true且复用solver_node_id=25。详见 [收口报告](../test/reports/issue-ledger-close-20260916.md)。
- 2026-09-16 十景点质量（H3，ADR-0027，已提交99e5ac4）：恢复跨日可行性后重平衡实际负载；固定场次日执行完整用餐/普通建议时长/下午展开；真实航次保留星期和有效日期，撤销错误合窗。详见 [质量报告](../test/reports/solver-quality-20260916.md)。
- 2026-09-16 七景点近邻（已提交731da1b）：OD强近邻在分天再平衡时保留；7点浏览器生成和两组近邻同日验证完成，历史细节见本月归档。

## 下一步（按顺序）

1. 完成 G7-R0.2-05-03 / R0.2-07：对已选定的 12 条代表性候选完成六项审核准备度、Projection、批次发布与用户端可见性回归。
2. 扩展研究目录至 50–75 条 `human_verified` Place，达到 G7-R1 研究最低目录门槛。
3. 实施 R0.2-06 按需真实有向 OD 子图：候选过滤、真实 OD 获取、缓存、不可变子图 hash、Revision 回放，缺边不填 0。
4. 进入 R0.3 服务器全栈 Compose/HTTPS/环境锁定；G1 真实用户发现研究可并行准备，并在 R1 外部招募前关闭。

## 本地运行验证（2026-09-16）

- API8000/8001、管理端5173、H5 10086已启动本轮代码；API在平湖秋月v4发布后已重启清理发布目录缓存，`/health/ready` 均为200。浏览器最新Revision `revision_a25a75eaeef543519c811f0d5a047106`，日期09-30至10-02；10安排/0未排入。日志在 `var/reports/services-20260916-cleanup/`。

## 活跃风险

- `SOLVER-QUALITY-005` 新观察：平湖秋月与断桥残雪已同日，但同日内方向仍由近似OD决定，当前可能为断桥→平湖；未违反 C1/C2/C4/C5/C6，待真实有向OD或显式西湖游线规则支持后优化。
- 本地近似OD仍不是实时路网；本轮只修正“未知近似短边误展示为步行”的标签与缓冲，不替代R0.2-06真实有向OD子图。
- 2026-09-10 提交核对仍需裁决：S6 sessionStorage + /me 会话恢复与 ADR-0020 持久化禁令存在边界差异；几何修复的客户端文案与 error-messages.md 单一文案源存在边界差异。
- 2026-09-11 只读核对：原 12 条批次 10 published / 2 candidate（杭州博物馆 027、良渚博物院 052，均无更新版本）；钱江新城灯光秀 048 的时间证据差异单独保留，不自动修改或豁免。

- Gate 1 存在真实用户研究补证债务：无真实访谈纪要与可追溯结论，M1 最终决策前必须完成 8–10 名目标用户发现研究，不得倒填。
- 历史账本记载的测试计数互相矛盾（352/363/367/370/…/432），以本文件顶部稳定测试基线为准；旧计数属阶段性快照，不代表回退。
- 服务器真实 MySQL 已通过 readiness 核对至 `0016_expand_alembic_version`；后续迁移或部署仍需保留 readiness、备份与隔离恢复核对。
- H1–H12 全部「未验证」；自动化测试、Chrome 验收或团队内部判断均不能冒充 H3/H11 的真实用户证据。
- Windows 偶发 `WinError 10055` 套接字错误为环境 flaky（隔离复跑即过），非业务回归。

## In-flight 区（并行任务登记）

| 任务 | 分支 | 触碰文件 | 状态 |
|---|---|---|---|
| 问题清单剩余四项收口（H3，接续本会话） | dev | `src/`、`tests/`存量类型修复；交通Provider与展示适配/参数及对应测试；地点发布通过业务接口；CURRENT/归档/改造计划/报告 | 已完成待提交；TYPE-001/OD-QUALITY-001/ADMIN-DATA-001/DATA-PLACE-002/SOLVER-QUALITY-004关闭；SOLVER-QUALITY-005登记后续 |
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

- 研究库 `.local/research.db`：平湖秋月最新 published v4=`place_revision_5ccfec95107f4757a5d112f59410cdc1`，Projection=`solver_projection_f46fb0c9da824b2bae7de03c3a65e582`，`data_verified=true`、`solver_node_id=25`；浙江省博物馆孤山馆区 published v4 为室内。
- 求解器契约：`solver-p1-v2 / trip-result-v2 / constraints-p1-v8 / parameters-p1-2026-09-16b`；历史 Revision 不迁移、不覆盖、不原地重算。
- Gate 7 protocol 规范化 SHA-256：`b791f0558dfc93af4cc919ec6dd9b09d1251f8f1d54b7bc0bb8809eade742d89`。
- 正式发布 bundle：`var/published/hangzhou-published-2026-08-27-v1.json`（7 景点 human_verified 坐标 + 42/42 高德 OD + 真实和风三日天气）。
- 本机禁止部署/启动 MySQL/Redis；本地开发组合根用明确标注的近似 fixture，生产组合根只加载严格验证的 published 快照。

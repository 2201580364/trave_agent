# 项目状态与续接记录

> 本文件是每次任务结束时必须更新的统一状态入口。新会话先读本文件，再按“下一步”继续。

跨里程碑稳定路线、阶段依赖和完成定义见 [项目完整路线图](project-roadmap.md)；本文件保留每轮执行账本和最新续接点。

## 术语

### 2026-08-30 续接进度（O05 开放时间与固定场次）

`G7-R0.2-05-02` 正在实施：审核工作流、Revision 版本化编辑、O04 几何/访问点写入与逐项审核以及 Projection 级发布入口已经落地并提交。当前进入 O05 开放时间与固定场次，Revision evidence 已装配周规则、固定闭馆日和日期例外，并在独立 `admin-web` 详情页形成与 O04 分离降级的只读证据面；写入、逐项审核和指定日期解析预览仍待下一切片。O01 待办摘要、O06 来源、O07 关系和批量审核仍待后续推进。本机 SQLite 已迁移到 `0010_place_revision_version`，服务器 MySQL/Redis 未连接。

本轮 O04 只读证据收口（2026-08-30）：发布上下文现在会收集 Revision、Geometry、AccessPoint 和 TimeRule 的完整来源依赖闭包，并校验来源与当前 Place 的归属；跨 Place 的 active 来源稳定返回 `SOURCE_RECORD_PLACE_MISMATCH`，缺失或 inactive 来源仍返回 `MISSING_SOURCE_RECORD`。证据接口只返回当前 Place 的来源摘要，几何和访问点逐行提供 `source_record_valid`，Projection 按当前 Revision/Place 过滤并以 `projection_id` 稳定排序。来源 URL 已覆盖用户信息、fragment、credential-like 查询参数、非法端口和 IPv6 方括号边界。O03 Revision 基础详情与 O04 Evidence 已独立加载，Evidence 暂时不可用时不会清空基础事实或审核操作。Google Chrome 管理会话和 O04 页面已完成可视化复核，控制台新增 warn/error 为 0。

| 术语 | 含义 |
|---|---|
| `M1–M4` | 产品路线里程碑；M1 是最小可用产品，M2 是信息与决策增强，M3 是全流程出行服务，M4 是记忆与生态 |
| `OM1–OM4` | 管理侧能力里程碑；依次支撑研究数据/发布、多目录/媒体、社区/实时服务、共创/AI 内容治理 |
| `P0` | 当前里程碑的阻塞优先级；缺失时无法形成首个可用闭环或无法验证核心假设 |
| `P1` | 当前里程碑的重要优先级；MVP 应具备，但可以晚于首个纵向切片 |
| `P2` | 增强优先级；不阻塞当前里程碑，可在证据充分后实现 |
| `G0–G7` | 假设驱动开发的证据 Gate，不等同于产品路线或实现优先级 |

历史机器标识 `solver-p1-v1`、`parameters-p1-*` 和 `DEFAULT_SOLVER_P1_CONTRACT` 必须保留；其中的 `p1/P1` 不再表示产品阶段命名。当前结构契约已按 ADR-0011 升级为 `solver-p1-v2 / trip-result-v2`；参数按 ADR-0013 保持 `parameters-p1-2026-08-26`，单日间节点下午展开语义按 ADR-0015 升级为 `constraints-p1-v5`；历史版本仅用于不可变 Revision 回放。

## 当前总状态

- 更新时间：2026-08-30
- 当前已提交基线：`0055dfc feat(admin): add revision evidence editing workflow`；工作区为 O05 时间证据只读切片，未包含凭证或密钥
- 产品里程碑：`M1 — 行程骨架验证`
- 里程碑判断：当前是 M1 后段，首个技术纵向切片 A6 已收口，但 M1 MVP 尚未经过 Gate 7 专家/用户验证，也尚未进入 M2
- 证据 Gate：Gate 6 求解器技术验证已通过；Gate 7 已进入 R0 验证准备，尚未招募或收集真实专家/用户证据
- 当前阶段：`Gate 7 — G7-R0.2-05-02 OM1 地点审核工作台 P0（当前节点）`
- 当前任务：在已完成的管理身份/API/RBAC/审计后端底座和独立 admin-web 安全操作面之上，完成 O01–O08 地点审核工作台 P0。O04 Geometry/AccessPoint candidate 写入、软停用、逐项 reviewer 审核和发布门禁已完成；当前实现 O05 时间证据面，先确保周规则、闭馆日、日期例外按 Revision/Place 边界可见且可追溯，再进入写入审核与解析预览。72 条研究数据不得通过 SQL 手工改状态，未审核依赖继续阻断发布；本机继续禁止部署或启动 Redis/MySQL 服务
- 总体判断：A6-9.1 至 A6-9.4、G7-R0.1、R0.2-01～04、R0.2-05-01A 和 R0.2-05-01B 已完成；R0.2-05-02 已完成审核工作流核心、O08 队列首版、O02 候选清单首版、O03 Revision 详情、O04 写入/逐项审核、候选分页以及 Revision→重新审核→Projection 发布业务闭环。O05 只读时间证据装配、页面展示、自动化回归和 Chrome 验收也已完成；仍缺 O05 写入/逐项审核/指定日期预览、O01、O06–O07、72 个 candidate 批量审核、OD 扩容、独立 research snapshot 发布、应用部署和 dry run，不能宣称 OM1、Gate 7、M1 MVP 或稳定生产已完成

M1 产品闭环核对：杭州单城入口、一键生成、结果保存/恢复、“替换景点→完整重求解→新 Revision”、“我的行程→最新恢复→历史只读回看”、“当前 Revision→安全计划分享→公开查看→参考复制”和“当前 Revision→整体/节点结构化反馈”均已完成工程实现与真实 Chrome 验收；到离交通、节奏/同行人群、景点筛选仍是首切片简化实现。M1 产品收口主队列工程完成 4/4；必须先准备并执行 Gate 7，不能仅凭工程完成直接跳转 M2。

本轮文档复审结论（2026-08-29）：

- 已新增 [项目完整路线图](project-roadmap.md) V1.0，将产品里程碑 `M1–M4`、证据 Gate `G0–G7`、工程切片 `A1–A6` 和 Gate 7 研究轮次 `R0–R3` 统一到一份依赖路线；
- 已审计 Gate 证据：G3–G6 的技术证据成立，但 Gate 1 只有研究计划、没有真实访谈纪要、样本说明和 H4 结论，属于必须在 M1 最终决策前关闭的证据债务；计划完成 8–10 名目标用户发现研究，不倒填、不用 AI 或 H3 测试代替；
- 已将产品全景升级到 V2.4，统一 `M1–M4` 与 `P0–P2` 语义，按 ADR-0004 修正体力软约束和 C1/C2/C4/C5/C6 硬约束，按 ADR-0018 修正数据治理、访问点与求解投影边界；
- 已把数据规模拆为两层：G7-R1 研究最低目录约 50–75 个 `human_verified` Place，M1 受控上线目录原则上 80–120 个；二者均不允许用未经来源登记或未经审核的数据凑数；
- 已同步功能完整性审查 V1.2、用户功能 V3.5、管理端功能 V1.1、UI/交互 V1.4、架构 V1.4、API V2.7、数据模型 V2.9、测试硬/软约束口径、开放时间目录门槛和高德 7 点正式发布状态；
- 已接受 ADR-0019，建立 OM1–OM4 管理侧路线、ADM-* 功能树、O00–O16 页面族和独立管理 API/RBAC/业务审计边界；R0.2-04 不等待管理端，R0.2-05 批量 human_verified 前必须完成 OM1 P0 审核闭环；
- 文档复审完成后已依次关闭 `G7-R0.2-02`、`G7-R0.2-03` 和 R0.2-04；R0.2-05-01A 管理身份/API/审计后端底座与 R0.2-05-01B 管理 Web 壳均已实现并验证，当前转入 05-02 地点审核工作台，不是批量发布、应用部署或 M2 功能实现。
- G1 发现研究不依赖 H5，可与 R0.2–R0.4 并行组织，但必须在 R1 外部参与者招募锁定前关闭，以免用未经校准的目标画像开展形成性/确认性测试；它不改变当前工程节点。
- 文档复审验证：Gate 7 environment/evidence 定向回归 `19/19` 通过；protocol 规范化 SHA-256 保持 `b791f0558dfc93af4cc919ec6dd9b09d1251f8f1d54b7bc0bb8809eade742d89` 且协议文件无 diff；全部 docs Markdown 相对链接可解析，269 个三级功能 ID 和 ADR 编号无重复，`git diff --check` 与敏感信息扫描通过。由于本轮不改运行代码，未重复执行全量 306 项技术基线。

## 已完成

| 工作流 | 状态 | 证据 |
|---|---|---|
| G3 求解器 Spike | 完成 | `spike/` 历史证据 |
| G4 求解器设计与约束分级 | 完成 | ADR-0003/0004 |
| G5 C1/C2/C4/C5/C6 与分层求解 | 阶段性完成 | 核心能力已通过 Gate 6；后续可根据应用集成、真实数据和用户验证继续修复或演进 |
| 日志与审计 | 完成 | 模块级、按级别每日文件、月度压缩归档 |
| Gate 6 Golden/降级/性能/接近度 | 通过 | `docs/test/reports/` |
| M1 求解器对外契约 | 已稳定并版本化 | ADR-0009/0011/0012/0013/0015；当前 `solver-p1-v2 / constraints-p1-v5 / parameters-p1-2026-08-26`，保留历史版本回放 |
| A1 功能模块设计 | 完成并持续同步（V3.5） | 14 个跨里程碑用户/平台一级功能域；新增 OM1–OM4 管理路线映射，详细管理功能见 `docs/product/管理端功能模块设计.md` |
| 项目文档体系与完整路线复审 | 完成（路线图 V1.0） | 统一 M/G/A/R 四套坐标、G0–G7 证据审计、M1 剩余路线、M2–M4 工作包、完成定义和每轮更新规则；识别 Gate 1 真实用户证据债务，见 `docs/process/project-roadmap.md` |
| 产品功能完整性复审 | 完成并持续同步（V1.2） | 补齐评论、小记/回顾和地点数据审核管理端三类缺口，见 `docs/product/产品功能完整性审查.md` |
| 管理端产品设计与后端底座 | OM1–OM4 路线完成；R0.2-05-01B 管理 Web 壳完成 | ADR-0019、ADR-0020、ADM-1～ADM-13、O00–O16；独立管理身份/API/RBAC/审计与 admin-web 已实现，地点审核队列/候选清单/Revision 详情/O04 只读证据首版已接入，几何/访问点写入审核和发布页面待实现 |
| A2 信息架构与 UI 设计 | M1 用户端详细设计；OM1 管理端产品级 IA 完成（V1.4） | 保留用户端三模式；新增桌面管理布局、O00–O16 页面和响应式边界，见 `docs/product/信息架构与UI设计.md` |
| A3 交互流程与状态机 | M1 详细设计；OM1 核心流程登记（V1.4） | IF-01–IF-24 保持用户路线；新增 IF-26–IF-30 管理身份、编辑、审核、发布和裁决，见 `docs/product/交互流程与状态机设计.md` |
| A4 应用代码架构设计 | 完成并同步管理边界（V1.4） | 两套前端、用户/管理 API 分离、共享领域门禁；管理身份和审计底座已实现，Governance 审核/发布继续按后续工作包落地 |
| A6-9.1 景点替换与新 Revision | 完成并通过 Chrome 验收 | 结果页替换入口、完整重求解、同 Trip Revision 递增、幂等与并发冲突保护、Alembic 0003、375×812/1280×800 Chrome 回放 |
| A6-9.2 我的行程与历史 Revision | 完成并通过 Chrome 验收 | 匿名主体隔离列表、更新时间排序与分页、最新 Revision 恢复、历史只读回看、返回当前版本 |
| A6-9.3 计划分享首版 | 完成并通过 Chrome 验收 | 不可变 `plan-share-v1` 脱敏快照、HMAC 公开 token、幂等创建、公开只读链接、访客参考复制、375×812/1280×800 与 console 门禁 |
| A6-9.4 结构化反馈首版 | 完成并通过 Chrome 验收 | Revision/节点反馈、稳定 reason codes、intent 幂等与目标去重、节点归属校验、Alembic 0005、375×812/1280×800 与 console 门禁 |
| Gate 7 R0 验证准备 | R0.2-01～04 已完成 | ADR-0018、来源治理、0006 地点物理模型/发布门禁、72 个 candidate 和覆盖矩阵已完成；当前进入 OM1 管理身份/API/审计底座 |
| Gate 7 R0.2-02 来源治理 | 完成 | 5 个首批来源、58 字段机器字典、2 组排除清单、字段级 allowlist、校验 CLI、12 项测试和来源核验报告；conditional 只进 staging，未登记/待审/禁止来源 fail closed |
| Gate 7 R0.2-03 地点物理模型 | 完成 | `place_catalog` 领域模型、12 张 SQLAlchemy 表、Alembic `0006_place_catalog`、来源哈希绑定、candidate/human_verified/published 隔离、稳定 projection hash、发布门禁和 8 项测试 |
| Gate 7 R0.2-04 候选清单与覆盖矩阵 | 完成 | 72 个 candidate、11 区域、9 类别、18 夜间/固定时段、28 室内/雨天、24 非点状候选、11 组未裁决关系线索、确定性覆盖矩阵、CLI 和 7 项测试 |
| Gate 7 R0.2-05-01A 管理后端底座 | 完成 | 独立 AdminActor/Role/Session、scrypt、会话摘要、服务端 RBAC、管理员创建/角色乐观锁与幂等、追加式 AuditEvent、`/api/v1/admin` 和 Alembic 0007；6 项专项测试 |
| Gate 7 R0.2-05-01B 管理 Web 壳与安全操作面 | 完成 | ADR-0020 独立 `admin-web/`、O00 登录/超时、O16 管理员与角色、最小 O15 审计只读；token 仅存 React 内存；`npm run typecheck/test/build` 通过，全量 pytest 通过 |
| Gate 7 R0.2-05-02 地点审核工作台 P0 | 进行中 | `0008_place_review_workflow`、`0009_place_revision_review_flags`、72 条 candidate 导入、O08 审核队列首版、O02 候选地点清单首版（前后端分页）、O03 Revision 详情首版、O04 只读证据首版、跨 Place 来源发布门禁、Revision 版本化发布闭环和完整 Chrome 验收报告；O01、O04 写入/审核、O05–O07 证据面和批量审核待完成 |

最新稳定技术基线：上一轮全量 pytest `349/349` 通过；本轮已完成迁移链升级到 `0010_place_revision_version`，O04 新增测试仍待补齐。数据库 head/readiness 目标为 `0010_place_revision_version`，服务器真实 MySQL 仍保持 0002，未在本轮连接或迁移。普通匿名 token 无法访问管理 API；密码使用 scrypt，管理 token 只存 SHA-256；角色变化使旧会话失效；最后一个 admin_security 不可移除；管理审计与每日分级文件日志分离。Gate 6、A6、R0.2-02～04 的既有证据与 72 个 candidate 哈希均未改写。全仓 Ruff 仍有 37 项历史风格债（迁移、spike 和既有测试/求解器文件），strict mypy 历史债仍未清零；本轮已修改文件的 Ruff 仍需在实现完成后复跑。以上仍只是工程和验证准备证据，不证明 H3/H11 已被专家或用户证实。

状态口径：求解器**核心实现已阶段性完成**，不是永久冻结；M1 对外契约、约束语义和默认参数均已稳定并版本化。允许继续进行缺陷修复、内部重构、性能优化和基于真实验证的后续演进，但契约行为变化必须按 ADR-0009/ADR-0011 评审并升级相应版本。

## 正在进行

### Gate 7：专家/用户验证准备

- 状态：G7-R0.1、R0.2-01～04、R0.2-05-01A 和 R0.2-05-01B 已完成；当前执行节点为 R0.2-05-02 OM1 地点审核工作台 P0。首个真实 `locked` 环境尚未生成，尚未开始招募或收集真实用户数据；
- 当前输入：已通过 Gate 6 的求解器证据、A6 完整浏览器纵向切片、结构化 Revision/节点反馈能力；
- 已完成产物：`gate7-validation-plan.md`、专家评审表、用户主持脚本、`gate7-protocol-v1.json`、匿名 evidence validator/aggregate report、`gate7-research-environment-v1` manifest、锁定 CLI 和环境/evidence 绑定测试；
- 已完成数据底座：`hangzhou-m1-source-registry-v1`、58 字段字典、来源校验 CLI；`place_catalog` 领域模型；12 张地点表和 Alembic `0006_place_catalog`；candidate→published 依赖闭包门禁；`hangzhou-m1-candidate-catalog-v1` 的 72 个 candidate、覆盖矩阵和关系线索；
- 下一产物：R0.2-05-02 地点审核工作台 P0（O01–O08）；其后依次是 R0.2-05-03 批量采集审核、R0.2-06 OD 按需子图和 R0.2-07 OM1 发布中心/published research snapshot，再进入统一 Compose 的服务器 H5/HTTPS、locked manifest 与内部 dry run；
- 门禁原则：不得用自动化测试、Chrome 验收或团队内部主观判断冒充 H3/H11 的真实证据；Gate 7 结果决定 M1 补修、受控试运行或进入 M2，而不是预设一定晋级。

### G7-R0.2-02 来源治理与采集字段字典（2026-08-29）

- 新增 `data/governance/hangzhou-source-registry-v1.json`：登记 5 个首批来源，高德/和风为现有用途内 `approved`，杭州文旅/西湖管委会/杭州开放数据为 `conditional`；
- 新增 2 组排除清单：未获授权前禁止批量采集社交 UGC 和 OTA/评论页，不保存账号、评论全文、媒体、Cookie/token 或实时库存页面副本；
- 新增 `place-collection-field-dictionary-v1.json`：58 个地点、访问点、时间、体验、关系、趋势、OD、天气和 provenance 叶子字段，全部 `pii_allowed=false`；
- 新增生产侧 fail-closed 判定：`source_id + field_id + collection_mode + target_stage` 四元组同时通过才允许写入；conditional 只进 staging，未登记/待审/禁止来源稳定拒绝；
- 新增校验 CLI、12 项自动化测试、领域规范和来源核验报告；完成 Chrome 复核后的 registry 规范化哈希 `c0085129bbca7a38c963985a8c29ef7b857275d8ff833b53cca9b6207470d21a`，dictionary 哈希 `773a7db58357b0cda5a7f9fa1fbd6a1e3d7351288e7601bbd0196d084ee7ed3a`；
- 官方公开 HTTPS 核验覆盖杭州文旅、西湖管委会、杭州开放数据、高德文档/条款、和风服务条款/限制/归属/EULA；robots 404 不解释为采集许可，未稳定核验的浙江省博物馆和 OSM 未进入允许清单；
- 已使用用户指定的 Google Chrome 可用实例完成首批 5 个来源复核：杭州文旅和西湖管委会主办主体可见，西湖“我想游”栏目可见，杭州数据开放平台可打开 4 页通用许可协议，高德/和风官方文档与条款入口可见；三个政府/开放数据入口更新为 `reviewed + conditional`，不因页面可见而放宽 staging-only、逐页面和数据集级审查边界；
- 当时验证结果：全量 pytest `318/318`，新增范围 Ruff 和 strict mypy 通过；R0.2-02 随后完成并进入 R0.2-03。本记录保留阶段性证据，当前节点见文首状态。

### G7-R0.2-03 地点物理模型、迁移与发布边界（2026-08-29）

- 新增独立 `travel_agent.domain.place_catalog` 领域：Place、SourceRecord、Revision、Geometry、AccessPoint、TimeRule、Closure、DateException、Relation、SelectionExclusionGroup/Member 和 SolverPlaceProjection；现有 solver `Attraction` 与 7 点历史快照保持不变；
- 新增 `travel_agent.infrastructure.database.place_catalog`，在同一 SQLAlchemy Base/UoW 中注册 12 张地点表和仓储；来源记录强制绑定 registry/dictionary ID 与 SHA-256，conditional 来源不能构造 published target；
- `PlaceRevision` 使用 candidate/human_verified/published/retired 生命周期；访问点、几何、时间和关系分别保存 review status；同一快照的 solver node 与 PlaceRevision 都有唯一约束；
- 新增稳定 `canonical_projection_sha256`，哈希只覆盖不可变 solver 输入，不受 workflow 状态、时间戳或 JSON key 顺序影响；
- 发布仓储拒绝直接插入 published Revision/projection；唯一 `publish_projection` 路径加载来源、几何、访问点、时间规则和关系依赖闭包，稳定拒绝未审核端点、缺失时间、歧义场次、未裁决重叠、来源冲突和哈希漂移；
- 新增 Alembic `0006_place_catalog`，只追加表、索引、外键和唯一约束，不修改 0001–0005；readiness 和 Gate 7 environment 要求同步升级为 `0006_place_catalog`；服务器数据库仍保持 0002，本轮只在临时 SQLite 数据库执行空库 `upgrade head`；
- 新增 8 项专项测试，覆盖 conditional staging-only、稳定哈希、完整发布、端点/重叠/哈希拒绝、多场次拒绝、SQLAlchemy 重启持久化、直接 published 插入拒绝和 Alembic 0006 表结构；全量 pytest `326/326`，相关 Ruff 和 strict mypy 通过；
- R0.2-03 已完成；后续 R0.2-04 已建立候选清单与覆盖矩阵，但尚未采集或审核杭州 50–75 个研究 Place，尚未生成 published research snapshot。

### G7-R0.2-04 杭州候选清单与覆盖矩阵（2026-08-29）

- 新增 `hangzhou-m1-candidate-catalog-v1`：72 个 candidate，全部绑定 `hangzhou-m1-source-registry-v1` 与 58 字段字典的精确规范化哈希，统一使用 `gaode-web-service + api + staging`；
- 新增确定性覆盖矩阵：11 个旅行区域、9 个产品主类别、18 个夜间/固定时段、28 个室内/雨天、48 point、22 area、2 route；43 attraction、10 scenic_area、10 neighborhood、2 walking_route、2 market、3 show、2 experience；
- 新增 11 组 `unresolved` 关系线索，覆盖西湖/湖滨/苏堤、灵隐/飞来峰、西溪/洪园、清河坊/南宋御街、运河/桥西、城市阳台/灯光秀、宋城/千古情、九溪烟树/九溪十八涧等父子、重叠和同体验风险；
- 使用已授权高德 Web 服务低频真实查询；Key 只从 `.env` 注入。Git 忽略缓存仅保存选中候选字段，不保存带 Key URL或无界原始响应；西湖音乐喷泉复用 2026-08-27 已接受的高德 POI 证据；
- 自动拦截酒店/公寓、内部房间、管委会、商店、停车场、公交站等错误匹配；龙井村改用牌坊作为仍待审核的代表候选；“运河夜游/湘湖夜游”在缺少稳定同名 POI 时收敛为游船候选，不伪造夜间事实；
- `宋城千古情` Provider 名称包含“暂停开放”，已保留稳定风险标记；所有 area/route 仍保留“Provider point 不是地点几何”、访问点未审核、时间/时长未采集标记；
- 新增候选构建 CLI、校验 CLI、领域校验器和 7 项测试；catalog hash `48a16f6756706b3e0f1fee7dbf9bfaf9cbfeb5715c08dafbc11391982cadb368`，coverage hash `ced7cecc2e3227560f07916585669b4d1950d9499a8b8ca8f5d358b5cc848f67`；
- R0.2-04 退出条件已通过，但这只证明候选发现和覆盖充分。72 个候选尚未批量 human_verified、未进入求解器、未生成 published snapshot；当前进入 R0.2-05-01 管理身份/API/审计底座。

### OM1 管理端产品设计补齐（2026-08-29）

- 复核确认原功能域 7–9 只有数据运营/发布/审计能力定义，缺少人员可操作的管理产品；原 O10–O14 只属于 M3 内容治理，不能承担 M1 地点审核；
- 新增 `OM1–OM4` 管理侧里程碑、`ADM-*` 原子功能和 O00–O16 页面族；OM1 覆盖候选、地点事实、地图/入口、时间、来源、关系、Revision 审核、发布快照、RBAC 和审计；
- 新增 ADR-0019，接受“两套前端、共享后端领域能力、独立 `/api/v1/admin` 与管理员身份”的边界；管理端不能直连 MySQL，也不能通过通用 PATCH/SQL 写 published；
- 当时的 API V2.6 和数据模型 V2.8 登记了管理端逻辑契约；后续 R0.2-05-01A 已将 AdminActor/Role/Session 和追加式 AuditEvent 落到 API V2.7、数据模型 V2.9 与 Alembic 0007，ReviewTask/Decision、PublicationBatch 仍待实现；
- Gate 7 路线将 R0.2-05 拆为 05-01 管理底座、05-02 审核工作台和 05-03 批量采集审核；R0.2-04 候选发现已完成，当前正式进入 05-01；
- 该规划轮只修改文档；后续已开始管理后端实现，但 admin-web、地点审核和发布中心仍未完成，不能宣称 OM1 完成。

### G7-R0.2-05-01A 管理身份、管理 API 与结构化审计后端底座（2026-08-29）

- 新增独立 `travel_agent.domain.admin` 和 `application.admin` 边界；普通匿名主体与 AdminActor 不共享凭证、会话或自动升级路径；
- 管理员密码使用 Python 标准库 `hashlib.scrypt`，随机盐和算法参数随摘要保存；会话 token 使用 48 字节级高熵随机值，数据库只保存 SHA-256 摘要；
- 首个管理员仅在 `admin_actors` 为空时通过成对环境变量一次性引导；默认赋予 OM1 的 admin_security/data_editor/data_reviewer/data_publisher/research_viewer，不提前启用 OM3 content_moderator；
- 新增管理员创建、登录、当前身份、注销、列表、角色替换和审计查询端点；管理写入使用服务端权限校验、operation intent、规范化非敏感 operation digest 和 actor version 乐观锁；
- 角色变化同时递增 `version/session_version`，所有旧会话立即失效；最后一个有效 `admin_security` 不可移除；管理员创建、登录成功/拒绝、会话撤销、角色变更成功/拒绝均写结构化审计；
- 管理审计只保存 actor/action/target、前后 digest、受限理由、request/intent、结果和 UTC 时间，不保存初始密码、token 原值、API Key、完整第三方正文或用户研究原文；文件日志每日分级/月度压缩策略保持不变，两者职责分离；
- 新增 Alembic `0007_admin_identity_audit`，追加 admin_actors/admin_roles/admin_actor_roles/admin_sessions/admin_audit_events 5 张表并种下 6 个角色目录；0001–0006 未修改；readiness head 同步为 0007，服务器 MySQL 保持 0002；
- 新增 6 项专项测试，覆盖一次性引导、密码/token 摘要、普通 token 隔离、撤销、RBAC、管理员创建幂等、角色版本/旧会话失效、最后安全管理员保护、拒绝审计、敏感理由拦截和空库升级；专项 6/6、相关回归 32/32 通过；
- R0.2-05-01A 已完成。当前进入 05-01B 独立管理 Web 壳；O01–O08 地点审核、批量 human_verified、O09 发布中心和服务器迁移均未开始。

### G7-R0.2-05-01B 独立管理 Web 壳与安全操作面（2026-08-29）

- 新增并接受 ADR-0020：管理前端作为独立 `admin-web/` 工程，采用 React 19 + TypeScript + Vite + React Router + Ant Design + Vitest + Testing Library + `@testing-library/jest-dom`；依赖与构建产物不进入 Taro 用户包；
- 新增 O00 登录页、会话超时与安全退出；Bearer token 仅保存在 React 进程内存，不写入 `localStorage`、`sessionStorage`、Cookie、URL、日志或错误文本，页面刷新后必须重新登录；
- 新增 O16 管理员与角色页：管理员列表、创建管理员、角色调整、乐观锁冲突处理、高风险操作输入登录名二次确认；前端仅用权限改善交互，服务端 RBAC 仍是授权事实来源；
- 新增最小 O15 审计只读页：动作/目标/理由/结果/请求 ID 查询、分页与摘要详情；不提供编辑、删除或导出原始敏感内容；
- 新增 `AdminApi` 薄客户端和错误码映射；401/会话过期时清空内存主体并回登录页；本地 Vite 将 `/api` 与 `/health` 代理到 `127.0.0.1:8000`；
- 验证：admin-web `typecheck`、`5/5` Vitest、Vite 生产构建通过；后端全量 pytest `349/349` 通过；本轮未连接或迁移服务器 MySQL/Redis；
- R0.2-05-01B 已完成。下一节点为 R0.2-05-02 地点审核工作台 P0。

### G7-R0.2-05-02 地点审核工作台核心（2026-08-30，进行中）

- 新增 Alembic `0008_place_review_workflow`，建立 `place_review_tasks` 与追加式 `place_review_decisions`；ReviewTask 工作流状态与 PlaceRevision 生命周期保持分离，0001–0007 未改写；
- 新增 `PlaceReviewWorkflowService`：data_editor 可送审 candidate Revision，data_reviewer 可 approve/request_changes/cancel；approve 与 `candidate → human_verified` 在同一数据库事务完成，异常会回滚决定、Revision、任务和审计；
- 审核操作均写入 `AdminAuditEvent`，携带 request ID、operation intent、规范化 operation digest、前后摘要和稳定错误码；相同 intent 可安全重放，不同载荷冲突；任务使用 version 乐观锁，过期决定返回 409；
- 新增管理 API：`GET /review-tasks`、`POST /place-revisions/{revision_id}/review-tasks`、`POST /review-tasks/{task_id}/decisions`、`GET /review-tasks/{task_id}/decisions`；非 candidate Revision、未知任务和重复决定均有稳定错误语义；
- 独立 `admin-web` 新增审核队列入口：按任务状态筛选、查看任务/决定历史、执行通过/退回修改/关闭；前端不复制 Revision 状态规则，所有状态变更由服务端 RBAC、事务和乐观锁决定；
- 新增 O02 候选清单首版：`GET /api/v1/admin/candidates` 和 `GET /api/v1/admin/place-revisions/{revision_id}`，支持按 lifecycle status 查询并返回 Revision 基础事实、来源记录数量、冲突裁决和 solver eligibility；admin-web 提供候选列表、详情展开和只读边界；
- 新增 O03 Revision 详情首版：候选清单和审核队列均可跳转到独立详情页；按基础事实、体验/求解摘要、治理状态和发布阻断摘要分组展示，阻断判断只基于当前 API 字段，并明确标注 O04–O07 逐项证据尚未接入；
- 补齐地点 Revision 首版版本化闭环：`POST /places/{place_id}/revisions` 从指定基线创建新的 candidate，`PATCH /place-revisions/{revision_id}` 仅允许编辑 candidate 并重置审核/求解资格，随后可重新送审；创建、编辑、发布均记录 reason、前后摘要和 operation digest，重复 intent 同载荷安全重放、不同载荷返回冲突；
- 新增首版发布门检查与发布入口：`GET /place-revisions/{revision_id}/publication-checks` 返回稳定 `reason_codes`，`POST /place-revisions/{revision_id}/publications` 仅在 human_verified Revision、Projection 及其依赖闭包通过门禁后执行；门禁失败返回 `409 publication_gate_rejected` 和 `details.reason_codes`，不会改变 Revision/Projection 状态；当前能力仍是 Projection 级发布，不等同于 R0.2-07 的独立 research snapshot、城市当前指针、批次发布和回滚；
- 新增 Revision 版本化发布 Chrome 验收报告 `docs/test/reports/g7-r0.2-05-02-revision-publication-chrome-2026-08-30.md`：基线 Revision 送审/通过、新 Revision 通过管理端“新建修订”按钮创建、修改、重新送审、审核通过、publication check 和 Projection 发布均有本地 SQLite/审计证据；报告明确区分路径 A（已有 `human_verified` 直接发布）与路径 B（新建 candidate→修改→重新审核→发布）；
- 新增 O04 只读证据接口 `GET /api/v1/admin/place-revisions/{revision_id}/evidence`：按 Revision 外键稳定加载来源摘要、几何、访问点和可选 Projection；Projection 到达/离开端点只展示已有明确绑定，不自动从访问点列表推断；候选 Revision 无 Projection 时仍可查看已采集证据；
- admin-web Revision 详情新增 O04 分区：以表格展示几何类型/GeoJSON 摘要、访问点用途/坐标/审核状态、来源记录和 Projection 端点；本切片不引入地图 SDK，不新增任何绕过 Revision 审核生命周期的写入操作；
- O04 证据闭包已补强：来源查询限定当前 Place，并纳入几何/访问点引用；缺失、错绑或不可读取的来源通过 `missing_source_record_ids` 显式返回；来源 URL 在管理响应中移除用户信息/片段并脱敏 credential-like 查询参数；Projection 只选择当前 Revision 且 Place 归属一致的最新记录，并以 `projection_id` 作为同时间 tie-break；
- 候选地点清单已支持服务端分页：`GET /api/v1/admin/candidates` 返回 `limit`、`offset`、`total`，数据库按稳定创建时间/ID 顺序执行 `LIMIT/OFFSET`；admin-web 默认每页 20 条，可切换 50/100 条并按页请求，刷新回到第一页；
- 验证：审核与候选专项后端测试 `10/10`、O04 evidence API 专项测试 `1/1`（含缺失/跨 Place 来源、URL 脱敏、无认证和 Projection 稳定排序）、相关数据库测试 `12/12`、admin-web typecheck、Vitest `5/5`、Vite production build、全量 pytest `349/349` 和 `git diff --check` 通过；Chrome 已完成管理员登录后的首页、管理员/角色、审计中心（展开/动作筛选）、审核工作台、候选清单、退出和受保护路由验收，并完成 Revision 版本化发布路径从新建、编辑、送审到发布的 Chrome 操作；
- O04 Geometry/AccessPoint candidate 新增、编辑、软停用和逐项 reviewer approve/reject 已完成；Revision 级 approve 会检查全部 active O04 证据均已 human_verified，写入自动递增 Revision 版本并重置求解/审核资格；
- O05 只读时间证据面已实现：同一 evidence 接口返回 `time_rules`、`closures`、`date_exceptions`，三类来源均纳入当前 Place 依赖闭包并逐项标识有效性；admin-web 独立展示周规则、固定场次、闭馆日、日期例外及跨午夜“次日 +1440”语义，O04/O05 请求失败时分别降级；
- 当前剩余：O05 时间写入、逐项审核和指定日期解析预览，O01 待办摘要、O06 来源冲突、O07 关系裁决及 72 个 candidate 批量审核仍未完成；Revision 差异视图、证据依赖复制策略和独立 research snapshot 仍属于后续切片；本机不部署 MySQL/Redis。

- 下一切片：完成 O05 时间规则、闭馆日和日期例外的 candidate CRUD 与逐项 reviewer 审核；复用 Revision 乐观锁、operation intent、审计和开放 review task 门禁。之后由后端提供指定日期解析预览并把时间完整性纳入 Revision approve，不允许前端自行猜测日期覆盖或固定场次冲突。

### A4：应用代码架构设计

- 状态：已完成
- 核心产物：`docs/product/应用代码架构设计.md`
- 关键结论：模块化单体；首切片 inline executor；通过 GenerationExecutor 可替换 Celery；Trip/Revision/Intent/SolverRun 分离；SolverGateway 隔离已稳定并版本化的求解器契约；M2–M4 只保留边界、不创建空模块
- 完成度：100%

### A5：API 与持久化数据模型同步

- 状态：已完成
- 核心产物：`docs/specs/api-contract.md` V2.7、`docs/specs/data-model.md` V2.9
- 关键结论：用户侧草稿/Intent/Trip/Revision 资源分离；ADR-0018 通用地点边界已由 `place_catalog` 与 Alembic 0006 实现；OM1 管理身份/API/RBAC/审计由 0007 实现，审核任务和发布批次仍待后续迁移
- 完成度：100%

### A6：首个浏览器可操作纵向切片

- 状态：首个浏览器可操作纵向切片已完成
- 当前输入：A4 架构、A5 HTTP v1 契约与数据库模型、已稳定并版本化的求解器契约
- 首个实现切片：匿名会话 → 草稿 → 杭州景点 → GenerationIntent → inline SolverGateway → TripRevision → 恢复结果
- 已完成：A6-1 至 A6-8.2 技术纵向切片与真实基础设施；A6-9.1 景点替换和新 Revision；A6-9.2“我的行程”和历史只读回看；A6-9.3 安全计划分享首版；A6-9.4 Revision/节点结构化反馈；新增页面均已完成真实 Google Chrome 复验
- 浏览器进展：首轮 375px 门禁和本轮正式数据桌面 Chrome 回放均走通 P00→P04；正式回放使用 2026-08-27 至 2026-08-29 的真实和风天气、审核坐标和 42/42 高德 OD，验证返回上一步、按钮真实禁用/启用、7 景点选择、午晚餐、交通方式/距离/耗时、三日切换、13:30–16:00 湖滨、19:30 固定表演、刷新恢复和“＋规划新行程”；3/2/2 景点全部守恒且 0 个未排入
- 响应式与安全：375×812 完整页面通过；1280×800 下内容居中、无横向溢出、日期 Tab 三列等宽；健康路径控制台 0 error/warn；受控后端故障只展示稳定用户提示，不泄露 Token、request ID 或技术堆栈
- 下一步：按 G7-R0.2 先建设足够的杭州研究数据和可扩展 OD，再进入 R0.3 受控服务器 H5、R0.4 dry run；不能从 7 点技术快照直接跳到 G7-R1
- 完成度：100%（仅指首个纵向切片的技术实现、真实数据、浏览器和服务器基础设施验证，不代表 M1 MVP、正式公网发布或 Gate 7 已完成）

### A6-9.1 景点替换与新 Revision 工程实现（2026-08-28）

- 新增结果页“替换景点”入口和独立候选页；候选页排除当前已选景点，用户确认一次后完整重求解，不要求重新填写日期、交通或全量景点；
- 新增 `POST /api/v1/trips/{trip_id}/revisions/{revision_id}/attraction-replacements`，复制基准 Revision 对应草稿，仅替换目标景点并创建新的 GenerationIntent；
- GenerationIntent 新增 `target_trip_id/base_revision_id` 修订血缘；首次生成保持两个字段为空，历史 Intent/Revision 不迁移、不覆盖、不重算；
- ExecuteGeneration 成功时在同一 Trip 下创建 `revision_number + 1`，更新 `current_revision_id`；旧 Revision 继续可读；
- 完成事务使用 `trip_id + expected_revision_id` 条件更新当前版本；只有更新一行的发布者可以创建新 Revision，过期或并发修改稳定返回 `trip_revision_conflict`；相同幂等 ID 和相同替换动作不重复创建草稿、求解或 Revision；
- 新增 Alembic `0003_trip_revision_lineage`，为修订血缘增加可空列，并落实 `(trip_id, revision_number)` 唯一约束；本地 SQLite 从 0002 升级到 0003 通过；服务器真实 MySQL 仍保持已验收的 0002 基线，待下一次应用部署前执行 0003，当前未擅自变更服务器；
- 全量 pytest 当时由 275 增至 277 项通过；前端 TypeScript、H5 production build 和改动文件 Ruff 通过；入口仍约 304 KiB，保留既有 P1 性能项；
- 2026-08-28 已在用户明确确认的真实 Google Chrome 标签页完成补充验收：从 Revision 1 替换景点生成同 Trip Revision 2、旧版可读、刷新保持新版；375×812 与 1280×800 均无横向溢出，健康路径 console 0 warning/error；
- A6-9.1 浏览器门禁已关闭，后续不再保留“Chrome 复验待补”旧口径。

### A6-9.2 我的行程与历史 Revision（2026-08-28）

- `TripRepository` 新增按 `principal_id`、`updated_at DESC, trip_id ASC` 的稳定分页查询；`TripRevisionRepository` 新增按 `revision_number DESC` 的历史查询，SQLAlchemy 与内存适配器保持一致；
- 新增 `GET /api/v1/trips?limit=&offset=` 和 `GET /api/v1/trips/{trip_id}/revisions`；所有查询先校验主体归属，越权与不存在继续统一为 404；列表只展示正式 Trip，不把草稿或失败 Intent 伪装成正常行程；
- `GET /api/v1/trips/{trip_id}` 收敛为用户可见摘要，不再返回 `principal_id` 和内部 `source_draft_id`；
- 前端新增 P06“我的行程”与“历史版本”页面：首页和行程详情均有明确入口；列表显示城市、日期、结果状态、已安排/未排入、当前版本、版本总数和最近更新时间；
- Zustand 将服务端事实 `currentRevisionId/currentRevisionNumber` 与临时 `revisionId` 查看指针分离；查看历史不会修改后端当前版本；历史详情显示只读提示，隐藏“替换景点”，支持一键返回当前版本；
- 自动化基线由 277 增至 284 项通过；前端 TypeScript、H5 production build、改动文件 Ruff 与 `git diff --check` 通过；H5 入口约 305 KiB，仍是既有 P1 性能项；
- 真实 Google Chrome 验收：列表存在两个 Trip 且最近更新的 Revision 2 Trip 在前；打开默认 Revision 2；历史列表为 2→1；历史第 1 版显示“当前版本是第 2 版”且无替换入口；返回和刷新均恢复 Revision 2；375×812 与 1280×800 无横向溢出，桌面两卡同排，完整刷新后新增 console warning/error 为 0；
- 临时 Chrome 视口已恢复；本轮本地 FastAPI/H5 验收进程已停止，端口 8000/10086 无监听残留；未在本机安装或启动 MySQL/Redis；
- M1 产品收口主队列按“替换、我的行程、分享、反馈”统计为工程完成 2/4；下一主实现为 A6-9.3 计划分享。

### A6-9.3 计划分享首版（2026-08-28）

- 新增独立 Sharing 领域/应用/基础设施边界：`PlanShare`、创建/公开读取/访客复制处理器、SQLAlchemy/内存仓储和 `HmacPlanShareTokenCodec`；未把分享状态塞入 TripRevision，也未复用 M2 旅程回顾或 M4 自动游记资源；
- 创建接口 `POST /api/v1/trips/{trip_id}/plan-shares` 使用 `plan_share_intent_id` 幂等；同一 intent/Trip/Revision/模板重试返回同一对象和 token，冲突稳定返回 `409 plan_share_intent_conflict`；
- 分享在创建时生成并保存不可变 `plan-share-v1/planned_itinerary` 白名单快照，只包含城市、日期、Revision 编号、每日景点名称、粗粒度时段/时长、固定场次、天气和计数；不包含匿名 access token、主体、Trip/Revision、内部 node/attraction ID、坐标、OD、私人交通或未来小记；
- 公开 token 为 `ps1.<plan_share_id>.<HMAC-SHA256>`；数据库只保存 SHA-256 摘要。生产组合根新增 `TRAVEL_AGENT_PLAN_SHARE_TOKEN_SECRET`，少于 32 字节 fail-fast；本地开发只使用明确标注的 local-only 密钥；
- 新增无认证 `GET /api/v1/plan-shares/{public_token}`，响应 `Cache-Control: no-store` 且不回显 token；新增认证后的 `POST /api/v1/plan-shares/{public_token}/draft-copies`，从该 Revision 对应 GenerationIntent 的不可变输入快照复制城市和景点集合，不读取可变源草稿当前值；新草稿 `travel_facts` 为 JSON null、时段偏好为空，访客必须重新确认日期和交通；
- 新增 Alembic `0004_plan_shares`，readiness 期望版本同步升级为 0004；空库升级、跨 SQLAlchemy 会话快照恢复和 token hash 查询已验证。服务器真实 MySQL 未在本轮擅自迁移，仍停在 0002；下次应用发布前必须按 0003→0004 顺序升级；
- 前端新增 `PlanShareCard`、作者分享预览页和公开访客页；当前 Revision 详情显示“分享计划”，历史 Revision 首版不显示入口；公开页明确“出发前计划、非实际到访”，提供“以此为参考新建行程”；
- 自动化：A6-9.3 定向 26 项、全量 282 项、改动文件 Ruff、前端 TypeScript 和 H5 production build 全部通过；H5 入口约 306 KiB 的既有性能警告继续登记为 P1；
- 真实 Google Chrome：从当前 Revision 2 生成分享，核对脱敏卡片、公开访问和访客复制；375×812 与 1280×800 无横向溢出，移动端底部回流按钮可自然滚动到达，完整刷新后新增 console warning/error 为 0；
- A6-9.3 首版完成口径是“不可变计划分享对象 + 安全公开链接 + HTML/CSS 模板化卡片 + 访客参考复制”。PNG/JPEG 导出、二维码/小程序码、保存相册、微信原生分享、作者撤回和转化埋点登记为 A6-9.3.1，当前不得宣称精美图片卡片/小程序码已全部完成；
- M1 产品收口主队列按“替换、我的行程、分享、反馈”统计为工程完成 3/4；下一主实现为 A6-9.4 结构化反馈。

### A6-9.4 结构化反馈首版（2026-08-28）

- 新增独立 Feedback 领域/应用/基础设施边界：`Feedback`、整体/节点提交处理器、SQLAlchemy/内存仓储和统一领域载荷校验；未把反馈写回 TripRevision，也未复用 M3 景点评分/评论资源；
- 新增 `POST /api/v1/trips/{trip_id}/feedback` 与 `POST /api/v1/trips/{trip_id}/revisions/{revision_id}/nodes/{node_id}/feedback`；整体支持合理/一般/不合理、六类问题多选和 500 字说明，节点支持安排得好/需要改进、单原因和说明；
- 客户端按规范化 payload fingerprint 复用 `feedback_intent_id`；服务端同 intent/同载荷稳定重试，同 intent/不同载荷返回 `409 feedback_intent_conflict`；同主体/Revision/目标只保留首份并返回 `deduplicated=true`，首版不提供编辑或覆盖流程；
- 节点必须真实存在于准确 Revision 的不可变 `result_snapshot`；Trip/Revision/node 越权或不匹配统一返回 404。应用层在目标去重前执行领域载荷校验，非法直接调用不会被去重分支吞掉；
- 新增 Alembic `0005_feedbacks`，包含 intent 唯一约束和 `(principal_id, revision_id, target_key)` 唯一约束；该节点当时将 readiness 期望版本升级为 0005。服务器真实 MySQL 未擅自迁移，仍停在 0002；随着后续 0006/0007，正式迁移顺序现为 0003→0004→0005→0006→0007；
- 前端当前 Revision 的每个景点卡片下显示节点反馈，行程依据后显示整体反馈；历史 Revision 不显示反馈或替换入口。成功和去重均转为明确只读状态，并说明反馈不会成为公开景点评分或评论；
- 自动化：反馈/HTTP/SQLAlchemy/readiness 定向 22 项、全量 287 项、改动文件 Ruff、前端 TypeScript 和 H5 production build 全部通过；H5 入口约 306 KiB 的既有性能警告继续登记为 P1；
- 真实 Google Chrome：375×812 下完成节点“需要改进 + 时间太赶 + 说明”和整体“不合理 + 路线太绕/节奏 + 说明”提交；刷新后以新 intent 提交相同目标均显示去重且 SQLite 始终只有 2 条记录；历史第 1 版的节点反馈、整体反馈和替换入口计数均为 0；375×812 与 1280×800 无横向溢出，完整刷新后 console warning/error 为 0；临时 viewport 已恢复，本地 FastAPI/H5 验收进程已停止，8000/10086 无监听残留；
- M1 产品收口主队列按“替换、我的行程、分享、反馈”统计为工程完成 4/4；A6 首个浏览器可操作纵向切片收口，下一阶段为 Gate 7 准备，不能直接宣称 M1 已完成。

### Gate 7 R0 验证准备 V1（2026-08-28）

- 新增 `docs/test/gate7-validation-plan.md`，把 Gate 7 拆为 R0 准备、R1 领域专家/8–12 人形成性测试、R2 `n>=21` 确认性测试和 R3 真实出行/分享漏斗试运行；明确自动化、Chrome、团队 dry run、AI 和 synthetic fixture 均不能冒充目标用户证据；
- H3 沿用登记册门槛：外部目标用户 `n>=21`，认可率 `>=70%` 支持、`<50%` 推翻、`50%–69%` 需调整；开放 blocker 时不能以认可率补偿。H2 必须等真实出行回访，H11 在缺公开环境、独立接收者和转化事件时稳定标记 `not_evaluable`；
- 新增领域专家独立评审表和用户主持脚本，覆盖 T01–T10、标准一级/二级 assistance、H3 主问题、退出/反例保留、分享隐私理解和 Revision/节点问题引用；
- 新增 `gate7-protocol-v1.json`，预注册 protocol ID、阈值、角色、问题严重度、归因和仓库禁止字段；严重度使用 blocker/major/minor/observation，不与产品 P0/P1/P2 优先级混用；
- 新增 `travel_agent.evaluation.gate7` 和 `scripts/run_gate7_report.py`：校验 protocol SHA-256、时间区间、应用/数据/求解器版本、知情同意、样本资格、重复 H3 主指标、participant 引用、敏感字段、严重度/归因和 H11 readiness；输出不含 participant ID 的匿名聚合报告；
- 合成示例明确标记 `synthetic_fixture=true`，实际汇总结果为 `H3=synthetic_only / H11=not_evaluable / gate7_overall=not_decided_by_single_study`，不会制造虚假 Gate 7 通过报告；
- Gate 7 定向 9 项和全量 296 项测试通过；改动 Python Ruff、Gate 7 新增 4 个 Python 源/测试文件隔离 strict mypy、protocol/example SHA-256 一致性和 `git diff --check` 均通过；pytest 结束时仅出现沙箱无权清理宿主临时目录符号链接的非测试失败提示，不影响 296 项通过结论；
- 当前只完成 R0 设计和机器工具，尚未锁定外部测试部署版本、建立受控原始材料空间或招募真实参与者；H1/H2/H3/H6/H7/H11 状态均未因本轮准备工作改为已验证。

### Gate 7 R0.1 研究环境锁定（2026-08-28）

- 新增 `gate7-research-environment-v1`：固定 study phase、Git commit/clean 状态、reviewed protocol hash、应用/结果/solver/constraint/parameter 版本、published 数据及 canonical hash、数据库实际/要求 revision、前端构建类型/目录 hash、证据存储类型和限制；manifest 只保存非敏感版本事实；
- 新增 `travel_agent.evaluation.gate7_environment` 和 `scripts/lock_gate7_environment.py`。状态由事实自动推导：脏工作树、数据库 revision 不一致或缺前端产物为 `candidate`；正式形成性/确认性/field pilot 使用 candidate/synthetic 数据为 `invalid`；只有门禁全部满足才是 `locked`；
- 将 reviewed protocol canonical SHA-256 固化为 `b791f0558dfc93af4cc919ec6dd9b09d1251f8f1d54b7bc0bb8809eade742d89`，协议漂移会阻止锁定；该节点当时要求数据库 revision 为 `0005_feedbacks`，当前要求已升级为 `0007_admin_identity_audit`；
- 锁定 manifest 若输出到仓库内部，必须写入 Git 忽略路径，避免“检查时 clean、写入后立即 dirty”的自相矛盾。推荐路径为 `.local/gate7/<study_environment_id>/environment.json`；
- Gate 7 evidence 新增 `study_environment_id + environment_manifest_sha256` 精确引用。真实 evidence 必须绑定 `locked` manifest，且 study phase、六项版本、manifest 生成时间必须一致；synthetic dry run 仍不能形成 H3 支持结论；
- 隐私门禁使用严格字段白名单并拒绝 `.env`、API Key、密码、secret/token、私钥和带凭证 URL 等敏感文本；原始 evidence、录音、联系方式和精确私人行程继续禁止进入 Git；
- 新增 synthetic candidate manifest 示例并完成端到端聚合 dry run，结果保持 `H3=synthetic_only / H11=not_evaluable`；新增环境定向测试覆盖 clean lock、dirty tree、数据库漂移、缺前端产物、protocol 漂移、synthetic 冒充正式数据、敏感字段、构建 hash 和 evidence 精确绑定；
- 实际 candidate 命令当时识别 `dirty_git_tree + database_revision_mismatch + frontend_artifact_missing`；锁定工具随后由提交 `8bbca5b` 固化。服务器仍为已验收的 0002，正式 artifact 和充分研究数据仍未形成，因此没有伪造首个正式 locked 环境，也没有连接服务器或读取 `.env`；
- 验证结果：Gate 7 定向 19 项、全量 306 项、改动范围 Ruff、4 个改动源/脚本文件隔离 strict mypy、synthetic manifest→evidence→aggregate 端到端命令均通过；全仓 Ruff/strict mypy 的既有历史债仍保持独立登记；
- R0.1 当时确认 locked manifest 仍需 clean commit、正式 H5 artifact 和服务器迁移；2026-08-29 进一步评审发现 7 点数据不足，执行顺序已调整为先完成 R0.2 数据与 OD 扩容，再进行 R0.3 部署和最终环境锁定。

### Gate 7 R0.2～R0.4 数据、部署与 dry run 规划（2026-08-29）

- 新增 `docs/test/gate7-data-deployment-readiness-plan.md`，将 G7-R1 前置链明确为 R0.2 杭州研究数据与地点类型、R0.3 受控服务器 H5、R0.4 内部 dry run；不再把“环境锁机制完成”直接等同于可以招募；
- 渠道决策：微信小程序仍是 M1 目标上线形态，但正式备案、审核和公开发布不是 G7-R1 前置条件。R1 推荐使用受邀移动端 H5 + HTTPS；小程序体验版在形成性 blocker/major 基本关闭后补充验证微信渠道差异；
- 数据判断：当前 7 点/42 条有向 OD 只用于 A6/Gate 6 技术回归。G7-R1 初始门槛登记为 40–60 个 human_verified 点状地点、10–15 个区域/路线/市集/表演实体、至少 8 个地理区域和 8 类用户可感知类别；数量是可调整的研究准备门槛，发布必填完整、坐标/入口审核和时间规则解析仍要求 100%，未裁决重复/冲突为 0；
- 地点模型决策：ADR-0018 已接受 `places + access points + geometries + sources + revisions + relations + solver projections`；M1 每个可选 Place 最多投影为一个 solver 节点，有向 OD 使用 `origin.departure_access_point → destination.arrival_access_point`，不把西湖湖滨、街区、路线或夜市粗暴伪装为普通单坐标景点；
- 来源与爬取边界：优先官方文旅、场馆/景区官方信息、高德允许使用的服务和许可开放数据。未完成条款/版权/隐私评审前，不默认批量爬取社交平台页面，不保存账号、评论全文、未授权图片、Cookie/token 或个人信息；“网红”只作为带时间窗和来源数的趋势软信号；
- OD 扩容规划：7 点完整矩阵不能原样扩大为全城多模式 N²。R0.2 必须实现“候选过滤→实际选择/替换候选/锚点真实 OD→缓存→不可变子图 hash→Revision 回放”，缺边不得填 0，近似不得冒充高德；
- 天气口径：R1 先锁定未来标准场景天气以保持可比性；参与者真实日期若进入补充场景，必须使用独立数据快照和 environment manifest，不能复用 2026-08-27 历史天气；
- R0.3 服务器门禁：使用既有授权服务器和 Docker Compose，不在本机安装 MySQL/Redis；完成备份、迁移、FastAPI/H5、域名/HTTPS、身份隔离、Chrome 和恢复验收后才能生成 locked manifest。没有域名/TLS 时只允许主持人设备 dry run；
- R0.4 内部 dry run 不计入用户分母，必须覆盖 T01–T10、大数据量选择/替换、区域类型展示、manifest→evidence→report、隐私、弱网和失败恢复；开放 blocker 和影响核心任务的 major 为 0 后才能招募；
- 产品功能树 V3.4 新增地点类型、入口、solver projection、来源/staging、覆盖矩阵、趋势软信号、按需 OD 子图、研究数据发布、全栈 Compose 和 R0.2～R0.4 发布门禁；该规划节点的数据模型 V2.6 只同步 ADR-0018 逻辑边界，后续 R0.2-03 已在 V2.7 落地新表和迁移；
- 本轮只修改规划与 ADR 文档，不改 protocol、代码、数据库或服务器；已通过相对链接、三级功能 ID 唯一性、protocol canonical hash 和 `git diff --check` 复核，最新代码测试基线继续沿用提交 `8bbca5b` 前已通过的全量 306 项；
- R0.2-02、R0.2-03、R0.2-04 和 R0.2-05-01A 已在 2026-08-29 依次完成；当前执行任务为 `R0.2-05-01B O00/O16 管理 Web 壳`，其后才是审核工作台、批量事实审核、OD 改造和研究快照发布。

## 本轮完成（2026-08-25）

- 在真实 Chrome 375px 视口完成一次 P00→P04 全流程，确认晚间灯光秀可在晚餐留白存在时排入行程；
- 新增 `frontend/src/index.html`，修复 H5 构建退出成功但不生成可访问 HTML 的漏判；
- 为 P00–P04 五个页面显式导入页面 CSS，并修复 375px 下日期 Tab 每项占满整行的问题；
- 修复 ProductionSolverGateway 把“用户未指定景点日期”误解释为“全部偏好首日”的映射：现在根据首日/中间日/末日实际可用容量，以时长、体力和数量稳定派生默认日期；该变更是网关内部映射修复，不升级 `generation-input-v1` 或现有求解器契约版本；
- 新增三天七景点网关集成测试，验证每天非空、日间数量差不超过 1、景点守恒、重复求解稳定和结果哈希稳定；
- 空白日改为显示明确空状态，且没有景点时不再展示“晚餐已安排”；
- 全量测试由 188 增至 189 项通过；相关 Ruff 检查、前端 TypeScript 检查和 H5 production build 通过，`dist/index.html` 存在；
- FastAPI 与 Taro H5 本地服务已按新代码重新启动并通过 readiness/HTTP 200 检查；
- Chrome 重连后完成 A6-7 复验：新生成行程按 3/2/2 分布，灯光秀在 18:30 排入，三天日期切换和刷新恢复通过；历史 Revision 保持不可变，没有被修复逻辑原地覆盖；
- 新增“新建行程”入口：保留匿名身份和历史后端记录，仅一次性替换当前规划指针；修复初版同步清空状态触发的 Taro `insertBefore` 控制台错误；
- API 客户端补齐网络异常和空错误体保护，受控断开后端时页面展示稳定错误文案，不再暴露底层 `Cannot read properties of null`；
- 375×812 移动端和 1280×800 桌面端检查通过，临时浏览器 viewport 已恢复；健康路径控制台无 error/warn；
- A6-7 正式完成；当时下一步登记为 A6-8 真实 MySQL，A6-7.2 根据真实浏览器行程质量反馈将高德真实路网调整到 MySQL 联调之前。
- 非阻塞遗留：H5 production build 入口约 304 KiB，Webpack 给出 entrypoint size warning；登记为后续 P1 前端性能优化，不阻塞当前纵向切片或 A6-8。

### A6-7.1 浏览器体验问题修订

- 新增午餐软留白：网关只从求解结果中真实存在的 11:30–14:00 空档派生 60 分钟或降级 30 分钟午餐；没有空档时明确标记未能安排，不通过 UI 伪造；该可选结果字段不改变现有求解器硬约束和稳定版本标识；
- 晚餐与午餐在结果页同时展示建议时间，时间按 10 分钟粒度表达为“前后”，避免制造分钟级承诺；
- 本地近似 OD 调整为 18km/h、1.6 绕行系数、不同点位至少 5 分钟；短距离推荐步行，中距离推荐打车，长距离提示公交/地铁或打车；
- 所有近似交通明确提示“出发前用实时导航确认”，页面使用缓冲后接驳时间和区间表达，不再把近似原始分钟数当作真实路线；真实地图路线、明确公共交通方案仍属于 A6-8 之后的生产数据接入；
- 普通景点改为 30 分钟到达区间和人类可读的停留范围；固定时段表演保留明确场次，例如“18:30 场次”；
- P01/P02/P03 均增加返回首页/上一步入口，浏览器验证返回后已选景点状态不丢失；
- 修复 Taro Button 的伪禁用样式：不再使用会匹配 `disabled=false` 的属性选择器，改为显式禁用 class，并在事件处理层再次阻断；浏览器强制点击未选景点的“确认选择”后 URL 保持不变；
- “规划新行程”入口提升到行程详情首屏，用户无需先寻找首页；新建后保留匿名身份和历史 Revision，只替换当前规划指针；
- Chrome 新 Revision 验证：三天均有午餐留白；第 1 天浙江省博物馆→西湖湖滨显示打车 10–15 分钟，西湖湖滨→灯光秀显示步行 5–10 分钟；健康路径控制台 0 error/warn；
- 全量测试由 189 增至 190 项，相关 Ruff、TypeScript、H5 production build 和 `dist/index.html` 检查通过。

### A6-7.2 日内展开、真实路网与餐厅演进修订

- 新增 ADR-0010，将高德真实有向路网定为 `M1 / P0`；本地坐标近似只允许用于开发 fixture、自动化测试和外部 Provider 不可用时的透明降级；
- 高德 Provider 规格要求保存实际入口坐标、A→B/B→A 独立道路距离、步行/公交地铁/驾车模式、耗时、版本和抓取时间，并具备缓存、超时、限流和缺边降级；
- 午餐/晚餐采用分阶段方案：M1 先保留软留白；M2 支持选择具体餐厅，餐厅作为真实节点进入完整求解，成功后创建新 TripRevision，禁止旧 Revision 原地修改或前端插卡片假重排；
- 新增建议时长弹性和 `DAY_SPREAD` 软目标：单景点宽松日也尽量使用完整建议时长；两个及以上日间景点有真实余量时，在不改顺序、不加绕路和不破坏 C1/C2/C4/C5/C6 的前提下，把最低可玩时长扩展至建议时长，优先保留 60 分钟午餐空档，并稳定覆盖下午；
- 采用约 16:00 的展开目标和最多 60 分钟额外延后；固定晚间节点前继续保留真实接驳和完整晚餐；精修不可行时自动回退原硬可行时序；
- 固定窄窗口表演在窗口允许时使用完整发布时长，18:30–19:00 灯光秀不再只按 60% 最低时长展示；
- 前端普通景点主时间从容易误解为游览起止的“09:45–10:15”改为“约 09:50 到达”，并独立显示“计划停留约 X”；固定表演仍显示明确场次；
- 新增 HZ-GC-07：浙江省博物馆/西湖湖滨覆盖上午与下午、午餐空档至少 60 分钟、18:30 灯光秀和 90 分钟晚餐保留、硬约束零违反；
- Chrome 新 Revision 复验：第 2 天浙江省博物馆约 09:00 到达并计划停留 1.5–2 小时，西湖湖滨约 13:30 到达并计划停留约 2.5 小时，灯光秀保持 18:30 场次；午餐 11:30–12:30、晚餐 16:50–18:20 均保留；
- Chrome 同时确认历史 Revision 仍保持旧时序，只更新“约 HH:MM 到达/计划停留”展示语义；新软目标仅作用于新生成 Revision，符合不可变回放要求；
- 求解器外部结构保持 `solver-p1-v1`，软目标升级为 `constraints-p1-v2`，参数升级为 `parameters-p1-2026-08-25`；机器快照已重新生成，历史 Revision 继续保留原版本；
- 全量 193 项测试通过；Golden 7/7、降级 8/8、公开攻略综合接近度 0.975、数据校验 7/7、性能门禁通过；相关改动 Ruff 通过；前端 TypeScript 和 H5 production build 通过；
- H5 入口仍约 304 KiB，保留既有 P1 性能优化项；全项目 Ruff 仍存在与本轮无关的既有格式/规则债，本轮仅对改动文件执行并通过 Ruff。

### A6-8.1 高德真实路网 Provider 与结果契约 V2

- 新增 `GaodeSettings`，高德 Web 服务 Key 只从 `TRAVEL_AGENT_GAODE_API_KEY` 读取且不进入配置 `repr`；城市编码、超时、缓存 TTL、数据版本和启用模式均可配置；
- 新增步行、公交/地铁、驾车三类路线解析，按高德 `lng,lat` 顺序请求；A→B 与 B→A 独立构建，不假设有向 OD 对称；
- 实现稳定模式选择：2km/35min 内优先步行，公交/地铁不比驾车慢超过 15min 时优先公共交通，否则选择驾车；部分模式缺失时从实际可用结果中稳定选择；
- 实现成功结果 TTL 缓存，以及 timeout、rate_limited、http_error、api_error、no_route、invalid_response 分类；失败时可透明使用近似 Provider，结果保存结构化 `fallback_reason`，无回退时保留 OD 缺边；
- 高德联网仅发生在 OD 快照构建阶段；OR-Tools 搜索读取 `InMemoryTravelTimeProvider`，避免在求解循环中联网并保持确定性回放；
- `TravelTimeResult` 增加可兼容的 `travel_mode`、`distance_m` 和 `fallback_reason`；近似 Provider 同步输出明确的近似距离；
- Gateway 和前端类型支持真实 `walking/transit/driving`、估算交通模式、道路距离与降级原因；结果页可以展示“公交/地铁 · 约 8.2 公里 · 约 30–40 分钟”；
- 新增 ADR-0011，将当前契约升级为 `solver-p1-v2 / trip-result-v2`；约束继续为 `constraints-p1-v2`，参数继续为 `parameters-p1-2026-08-25`。历史 `solver-p1-v1 / trip-result-v1` Revision 不迁移、不覆盖、不重算；
- 新增高德离线 Provider 测试和 Gateway V2 映射测试，覆盖 Key 脱敏、缓存、限流、双向 OD、多模式选择、timeout 降级、缺边、真实交通方式/距离以及降级原因；
- 新增 `scripts/build_gaode_od_snapshot.py` 与 `docs/ops/gaode-od-snapshot.md`：真实请求必须显式传入 `--execute-live`，输入必须通过发布数据门禁，输出保存版本、双向边、模式、距离、失败统计和降级原因；缺边时以非零状态退出；
- 增加仓库根目录 `.env` 本地配置方案：`.env` 和 `.env.*` 默认被 Git 忽略，只有无真实凭证的 `.env.example` 可以提交；`python-dotenv` 以不覆盖进程环境的方式加载高德和数据库配置；
- 全量 211 项测试通过；Golden 7/7、降级 8/8、接近度 0.975、数据校验 7/7、性能门禁、改动文件 Ruff、TypeScript 和 H5 production build 全部通过；机器契约报告已生成 V2；
- 已完成首次真实联网严格构建：42/42 最终有向 OD 来自高德，0 approximate、0 missing；最终模式为 driving 30、transit 8、walking 4，快照未包含 Key；
- 追加公交诊断触发 25 次 `rate_limited`，当前停止继续调用；完整证据与风险见 `docs/test/reports/a6-8-1-gaode-live-validation-2026-08-26.md`；
- 真实快照进入 Gateway 后 7/7 景点排入、4/4 日内连接使用高德且 0 回退，但出现灵隐寺/飞来峰拆天和第三天跨区往返，确认分天默认偏好尚未使用 OD 成本，需在 A6-8.1 收口后才能进入生产发布。

### A6-8.1 真实 OD 行程质量与配额保护收口

- 新增 ADR-0012：默认分天从“只按时长/体力/数量平衡”升级为使用已发布有向 OD 的确定性 average-linkage 聚类；聚类只生成中性日期偏好，最终日期仍由 C1/C2/C4/C5 可用性、容量和跨天重分配决定；
- 缺一个方向的 OD 使用确定性惩罚，双向缺失使用大成本，禁止把缺边当作 0；最大簇大小为 `ceil(N / days)`，保证近邻聚合与每日容量可以同时成立；
- 修复 Step 3 分段目标：先求晚间段，日间 OR-Tools 顺序加入“日间末节点 → 晚间首节点”的终端 OD 成本；终端成本不重复进入时间维度，合并阶段继续负责真实到达时间和 C6；
- 使用既有真实快照纯离线回放，不再请求高德：稳定结果为“飞来峰→灵隐寺”“浙江省博物馆→西湖湖滨→湖滨晚间表演”“河坊街→雷峰塔”，7/7 景点守恒、0 未排入、4/4 连接均为高德；
- 修复前后由约 23,195m/109min 改善为 7,594m/50min，道路距离约减少 67%，接驳时间约减少 54%；
- 新增高德失败明细，后续报告可保存脱敏的 pair、mode、code、`infocode` 和发生时间，不保存 Key、带 Key URL 或请求参数；旧限流诊断因发生在修复前，仍无法追溯具体 `infocode`；
- 新增本机跨进程 JSON TTL 缓存，默认位于 `var/cache/gaode-routes.json`，缓存键包含起终坐标、模式、城市、数据版本和策略，使用临时文件替换原子写入；
- 软目标版本升级为 `constraints-p1-v3`；`solver-p1-v2 / trip-result-v2 / parameters-p1-2026-08-25` 不变。历史 Revision 和 V1/V2 标识不迁移、不覆盖、不原地重算；
- 全量 214 项测试通过；Golden 7/7、降级 8/8、接近度 0.975、数据校验 7/7、性能门禁、改动文件 Ruff、TypeScript 和 H5 production build 全部通过；`git diff --check` 无空白错误；
- 当前进度：A6 仍约 98%。真实 OD 算法质量缺陷已收口，生产 PublishedDataProvider 组合根已于 2026-08-27 补齐；A6-8.1 尚余入口坐标人工校准、正式快照审核/发布、配额看板/熔断；完成后进入 A6-8.2 真实 MySQL 与部署恢复。

### A6-8.1 路线点候选、分天负载与 JSON 发布适配器收口（2026-08-26）

- 使用高德 Web 服务 V3 对 7 个杭州景点执行真实 POI 候选审计；有效节流请求均返回 `status=1 / infocode=10000`。浙江省博物馆、西湖湖滨和音乐喷泉原 fixture 分别偏移约 636m、652m、755m，证明裸坐标不能直接作为生产游客点位；
- 新增路线点发布门禁：生产坐标至少保留高德 POI ID、点位类型、来源、抓取时间和审核状态；candidate 默认禁止进入正式构建，published 强制 `human_verified`；多门景区和开放街区仍需人工确认；
- 快照构建脚本增加缓存未命中请求节流，默认间隔 1.05 秒；候选点位严格真实重建耗时约 132.8 秒，42/42 高德、0 approximate、0 missing，4 次 transit `no_route` 由其他模式补齐，节流后无 rate limit；
- 真实候选 OD 首次形成 `3/3/1`；新增聚类后数量均衡，确保默认簇数量差不超过 1；继续新增建议游览时长均衡，只在数量保持 floor/ceil 且双向对称 OD 代价增量不超过 10 分钟时移动，避免拆散强近邻；
- 最终稳定结果为“飞来峰→灵隐寺”“浙江省博物馆→西湖湖滨→湖滨晚间表演”“雷峰塔→河坊街”，日数量 `2/3/2`，建议时长负载 `300/290/210min`，交通 `80min / 7,135m`，7/7 守恒、0 未排入、4/4 高德连接；结果哈希为 `98705e1a8e3a92c62eb415126015faa367efa997b589b40ce26af2c4cff2b687`；
- 新增 `JsonPublishedSolverDataProvider`：校验 SHA-256、版本、景点/外部 ID 唯一、路线点来源、candidate/published、人工审核、天气日期和完整有向 OD basis/version；加载后完全离线，不调用高德；
- 新增候选 bundle 构建器；审计天气必须显式确认并标记为 `audit_normal_fixture`，禁止伪称实时天气。候选 bundle 已离线回放通过，但不会被默认正式 Provider 加载；
- 新增 ADR-0013；结构契约和结果 schema 保持 `solver-p1-v2 / trip-result-v2`，软目标升级为 `constraints-p1-v4`，参数升级为 `parameters-p1-2026-08-26`，历史 V1/V2/V3 Revision 不迁移、不覆盖、不原地重算；
- 全量 226 项测试通过；Golden 7/7、降级 8/8、接近度 0.975、数据校验 7/7、性能门禁、改动文件 Ruff、TypeScript 和 H5 production build 全部通过；H5 仍只有既有 304 KiB 入口体积警告；
- 补跑全项目 strict mypy 后确认仍有 154 条既有类型债，涉及 27 个历史文件和 OR-Tools 无类型存根；该项尚非绿色 Gate，本轮未扩张为跨模块清债任务；
- 当前阶段结论：A6-8.1 的坐标候选、真实严格 OD、算法负载修复和 JSON 发布适配器已完成技术验证；正式发布仍等待路线点人工确认、真实天气、生产发布表、配额看板/熔断与跨机器缓存。A6 维持约 98%。

### A6-8.1 生产 PublishedDataProvider 组合根接入（2026-08-27）

- 尝试连接浏览器执行浙江省博物馆、灵隐寺/飞来峰和西湖湖滨路线点人工复核，但当前无已连接浏览器实例；相关点位继续保持 `manual_review_pending`，没有降级为自动审核或错误标记 `human_verified`；
- 新增 `PublishedSnapshotSettings` 和 `ProductionHttpSettings`，从环境显式读取快照根目录、M1 城市和发布版本；数据库和快照配置复用 `.env` 加载且不覆盖部署环境；
- 新增 `build_production_http_app()`：启动时先加载并完整验证发布快照，校验快照城市后再创建 FastAPI 应用；candidate、未审核坐标、缺文件、哈希/OD/版本错误或城市不一致均 fail-fast；
- 生产组合根不提供 `allow_candidates` 环境开关，candidate 只能通过审计代码显式加载；现有真实候选 bundle 已完成实物验证，生产组合根按预期拒绝；
- 新增 `scripts/run_published_app.py` 作为生产式 JSON 快照入口；数据库迁移继续要求启动前独立执行，不在服务进程中隐式修改 schema；
- `.env.example` 新增 `TRAVEL_AGENT_PUBLISHED_SNAPSHOT_ROOT/CITY_ID/SNAPSHOT_VERSION` 占位配置，不包含真实凭证或候选版本；本地 `build_local_dev_app()` 继续使用明确标注的近似 fixture，与生产入口分离；
- 新增生产组合根测试，覆盖环境加载、版本必填、正式快照构建、candidate 拒绝和城市不一致拒绝；
- 全量 232 项测试、Golden 7/7、降级 8/8、接近度 0.975、数据校验 7/7、性能、改动文件 Ruff、TypeScript 和 H5 production build 全部通过；全项目 strict mypy 仍为既有 154 条/27 文件，本轮新增文件没有直接类型错误；
- 当前阶段结论：生产 JSON Provider 接入路径已经打通，A6-8.1 不再缺少组合根实现；剩余阻塞收敛为路线点人工确认、正式天气/快照发布、配额治理和真实部署验证。A6 维持约 98%。

### A6-8.1 路线点浏览器复核与和风天气发布链路（2026-08-27）

- Chrome 控制通道已恢复，已在高德地图 Web 逐项检索并复核 7 个候选路线点；页面证据确认省博候选为“浙江省博物馆孤山馆区(南门)”、灵隐寺候选为“灵隐寺(进口)”、飞来峰候选为“飞来峰(1号门)”、湖滨候选对应湖滨公园，雷峰塔售票处、清河坊步行街和西湖音乐喷泉表演点语义也分别获得页面支持；
- 新增 `a6-8-1-gaode-browser-coordinate-review-2026-08-27.md`，记录查询、页面结果、点位语义和联游 OD 一致性；发布责任人于 2026-08-27 接受报告中的 7 个点位口径并授权生成新的 `human_verified` 坐标版本；
- 新增和风三日天气 Provider：配置 Key 脱敏、可配置 Location ID/HTTPS API Host/超时/数据版本，解析 `/v7/weather/3d`，要求三个唯一连续日期和带时区抓取时间，并分类 timeout/rate_limited/http_error/api_error/invalid_response；
- 固化 `qweather-severity-v1`：晴/多云等为 normal，普通雨雪/雷/雾/霾/沙尘为 advisory，暴雨/大暴雨/特大暴雨、暴雪、台风、龙卷风、冰雹、雷暴大风和强沙尘暴为 extreme；只有 `basis=forecast AND severity=extreme` 可驱动 C5 硬排除，climate 只做提示；
- 新增 `scripts/build_qweather_snapshot.py`，真实联网必须显式传入 `--execute-live`；快照保存 `condition_code/source_ref/fetched_at/provider_update_time/data_version/content_hash`，不保存或打印 Key；
- 正式 `JsonPublishedSolverDataProvider` 增加天气来源门禁：published 天气不能为空，必须带 condition、condition_code、source_ref 和带时区 fetched_at，`weather_basis` 含 audit/fixture 时拒绝；candidate 显式离线审计兼容性保持；
- 新增 `scripts/build_published_solver_snapshot.py`：只接受全量 `human_verified` 坐标、0 fallback/0 missing 的严格高德有向 OD、哈希有效且城市一致的和风三日 forecast；正式文件排他创建，禁止覆盖历史快照；
- 新增 ADR-0014 和 `docs/ops/qweather-snapshot.md`，明确三日之外必须使用正式气候基线或拒绝覆盖，禁止复制第三天预报、循环天气或补造晴天；当前尚未实现气候基线 Provider；
- 全量测试由 232 增至 255 项通过；Golden 7/7、降级 8/8、接近度 0.975、数据校验 7/7、性能门禁、本轮改动文件 Ruff、新增实现源文件隔离 strict mypy、前端 TypeScript 和 H5 production build 均通过；H5 仍有既有 304 KiB 警告，全仓 Ruff 仍有 46 个历史问题；
- 新增不可变审核坐标版本 `var/published/hangzhou-attractions-reviewed-2026-08-27-v1.json`：7 个点位均为 `human_verified`、`data_verified=true`、`conflict=false`；浙江省博物馆（孤山馆区）点位语义由候选态 `south_gate_candidate` 收口为 `south_gate`，旧候选文件保持不变；
- 使用新审核坐标真实重建 `gaode-hangzhou-reviewed-2026-08-27-v1`：42/42 有向 OD 均为高德结果，0 fallback、0 missing，模式分布为 walking 4、driving 27、transit 11；4 次 transit `no_route` 均由其他真实模式成功补齐，快照不含 Key 或带 Key 请求字段；
- 新审核 OD 已生成仅供离线审计的 candidate bundle；其天气仍为 `audit_normal_fixture`，只能通过显式 `allow_candidates=True` 加载，不能进入生产；
- 新审核 OD 离线求解保持 7/7 景点、0 未排入、0 硬约束违反和稳定结果哈希，但第三天形成“西湖湖滨 09:00–11:30、午餐 11:30–12:30、晚餐 17:52–19:22、表演 19:30”的时序，12:30–17:52 约 5 小时 22 分钟无安排；该体验回归必须在正式发布前收口，不能只因硬约束通过就判定路线质量通过；
- 当前 `.env` 尚未配置 `TRAVEL_AGENT_QWEATHER_API_KEY`，因此真实和风响应与正式杭州天气快照尚未验证。当前阶段结论：路线点人工确认和新严格 OD 已完成，天气与正式合并代码路径已完成离线闭环；A6 维持约 98%，当前优先项为真实和风天气与正式 bundle，剩余发布阻塞为和风真实凭证/响应、配额治理和真实部署。

### A6-8.1 单日间节点下午展开收口（2026-08-27）

- 新增 ADR-0015：当一天只有一个普通日间节点且存在固定晚间段时，在完整午餐、90 分钟晚餐、真实跨段 buffered OD、固定场次和 C1/C2/C4/C5/C6 均可保留的前提下，允许将日间节点稳定后移至约 16:00 离开；
- 多日间节点仍受 60 分钟局部移动上限约束；单节点没有日间内部顺序或 OD，不套用该局部上限。默认数值参数未变化，参数版本保持 `parameters-p1-2026-08-26`；软约束语义升级为 `constraints-p1-v5`，结构契约与结果 schema 保持 `solver-p1-v2 / trip-result-v2`；
- 新增 Step 3 单元测试：西湖湖滨 150 分钟 + 19:30 固定表演稳定得到 13:30–16:00；`last_entry=11:00` 反例保持 09:00 原时序，证明不会为覆盖下午突破 C2；
- 新增 HZ-GC-08，使用审核后真实湖滨 OD `walking / 386m / 6min`，验证 60 分钟午餐、150 分钟湖滨、90 分钟晚餐、19:30 表演和 0 硬约束违反；Golden 从 7/7 扩展为 8/8；
- 使用 `hangzhou-reviewed-od-audit-2026-08-27-v1` 完整离线回放：7/7 景点、0 未排入、0 数据拒绝、0 硬约束违反、结果哈希稳定；关键日为午餐 11:30–12:30、西湖湖滨 13:30–16:00、晚餐 17:52–19:22、表演 19:30–19:50，原 5 小时 22 分钟下午空白已消除；
- 全量 258 项测试、Golden 8/8、降级 8/8、接近度 0.975、数据校验 7/7、性能 P95 14.94ms/19.32ms、改动文件 Ruff、隔离 strict mypy、前端 TypeScript 和 H5 production build 全部通过；H5 保留既有约 304 KiB 入口体积警告；
- 回归证据见 `docs/test/reports/a6-8-1-reviewed-od-single-daytime-spread-2026-08-27.md`。当前 A6 仍约 98%，下一步是配置真实和风凭证、构建正式天气并发布不可变杭州 bundle。

### A6-8.1 和风 API KEY 请求头认证修订（2026-08-27）

- 根据和风当前官方文档，将 API KEY 从旧式 URL 查询参数 `?key=` 攻击面迁移为 `X-QW-Api-Key` 请求头；三日天气 URL 查询参数现在只包含杭州 `location=101210101`；
- `TRAVEL_AGENT_QWEATHER_BASE_URL` 改为必填专属 HTTPS Host，不再隐式回退到逐步停用的 `devapi.qweather.com`；含路径、查询参数、fragment、用户名或密码的 Host 会被拒绝，避免把 Key 或完整接口路径误写入基础地址；
- `.env.example` 改用无真实凭证的 `https://your-account-host.qweatherapi.com` 占位值；运维文档补充请求头认证与禁止 `?key=` 的安全口径；
- 新增 6 项测试，覆盖专属 Host 必填、危险 URL 拒绝、API KEY 只进入请求头以及 URL/params 无 Key；和风相关离线测试 20 项通过，全量测试由 258 增至 264 项，改动文件 Ruff、隔离 strict mypy 和 `git diff --check` 通过；
- 脱敏实物检查发现 `C:/Users/Administrator/CascadeProjects/trave_agent/.env` 当前仍只有数据库和高德变量，没有任何 `TRAVEL_AGENT_QWEATHER_*` 变量；因此未发起真实请求，也未生成天气或正式 published bundle。A6 维持约 98%，待用户将凭证保存到该文件后继续。

### A6-8.1 真实和风天气、正式 Published Snapshot 与生产回放收口（2026-08-27）

- 用户将和风 API Key、专属 API Host、杭州 Location ID、超时和数据版本实际保存到项目根目录 `.env`；脱敏加载确认 Key 非空且不进入 `repr`，Host 是无路径/query/fragment/用户信息的 HTTPS 主机；真实凭证和专属 Host 未进入回复、日志、测试报告或快照；
- 使用 `X-QW-Api-Key` 请求头真实调用和风 `/v7/weather/3d` 成功，生成不可变 `var/audit/qweather-hangzhou-2026-08-27-v1.json`；日期为 2026-08-27 至 2026-08-29，三个日期唯一、升序、连续，来源字段和内容哈希完整，天气依次为晴转小雨、中雨转多云、小雨转晴，均为 advisory；
- 以 7 个正式景点、7 个 `human_verified` 坐标、42/42 高德有向 OD 和真实天气合并 `var/published/hangzhou-published-2026-08-27-v1.json`；严格 `JsonPublishedSolverDataProvider` 加载通过，状态 `published`、哈希正确、0 fallback、0 missing；本地 `.env` 的正式版本选择器已切换到该不可变版本；
- 生产组合根/FastAPI 以配置数据库完成三日七景点端到端回放：readiness、数据库和身份均 ready，GenerationIntent completed，`complete_success / trip-result-v2`，7 个已选景点全部排入、0 未排入，三天 forecast/午餐/晚餐完整，跨景点连接均使用 gaode，TripRevision 持久化成功；验证过程产生的历史 Revision 保留且未覆盖；
- Chrome 使用 H5 production build 完成 P00→P04：P01/P02/P03 有返回入口，未选时 CTA 真实禁用、满足条件后真实启用，P04 有“＋规划新行程”；交通方式、距离和耗时范围可见；第三天为 13:30 西湖湖滨、约 2.5 小时，晚餐约 17:50–19:20，19:30 湖滨晚间表演；刷新后三日节点顺序稳定，控制台 0 warn/error；
- 后端全量 pytest、前端 TypeScript、H5 production build 和 `git diff --check` 通过；H5 仍保留既有约 304 KiB 入口警告。详细证据见 `docs/test/reports/a6-8-1-qweather-published-production-replay-2026-08-27.md`；
- 当前阶段结论：A6-8.1 的真实生产数据发布主链已经收口，A6 仍约 98%，接下来只处理配额看板、限流/熔断、跨机器缓存和旧快照继续服务，再进入 A6-8.2；Gate 7 与 M1 MVP 仍未完成。

### A6-8.1 Provider 治理与旧快照持续服务（2026-08-27）

- 修订 API、数据模型和功能模块文档的历史状态：HTTP v1、SQLAlchemy/Alembic、高德 Provider 和正式 Published Snapshot 均不再标记为“待实现”；明确 A6 约 98% 只表示首个技术纵向切片，不代表 M1 MVP；
- 新增 ADR-0016。生产组合根继续优先加载显式当前版本；仅按 `TRAVEL_AGENT_PUBLISHED_SNAPSHOT_FALLBACK_VERSIONS` 的声明顺序尝试已知良好旧版本，所有候选执行相同的 published、哈希、城市、坐标、天气和严格 OD 门禁；不扫描目录、不启用 candidate、不放宽验证；
- 发生旧版本回退时记录模块级 error 日志，并在 FastAPI `app.state` 暴露请求版本、选中版本和 `fallback_used`；当前与全部回退均无效时仍 fail-fast；
- 新增凭证无关的 `JsonProviderRequestGovernor`，使用进程间文件锁和原子 JSON 替换记录高德/和风按日安全预算、成功/失败计数、失败分类、跨进程最小请求间隔、连续失败和熔断截止时间；`rate_limited` 立即熔断，超时/HTTP/API/无效响应按阈值熔断；
- 高德缓存未命中请求与和风三日预报请求已接入统一治理回调；缓存命中不消耗请求预算。新增 `scripts/show_provider_governance.py`，可输出人类可读或 JSON 状态，状态文件不保存 Key、专属 Host 或完整请求参数；
- 新增环境配置 `TRAVEL_AGENT_GAODE_DAILY_REQUEST_BUDGET`、`TRAVEL_AGENT_QWEATHER_DAILY_REQUEST_BUDGET`、`TRAVEL_AGENT_PROVIDER_CIRCUIT_FAILURE_THRESHOLD`、`TRAVEL_AGENT_PROVIDER_CIRCUIT_OPEN_SECONDS` 和显式快照回退列表；
- 针对性 49 项测试通过；全量 pytest 由 264 增至 272 项通过；改动文件 Ruff 和隔离 strict mypy 通过。求解器输入输出和版本组合未变化，Gate 6 结果保持有效；
- 当前阶段结论：单机/共享文件系统上的配额、限流、熔断和旧快照继续服务代码闭环已完成；仍需跨机器共享后端、正式配额来源或集中看板以及多实例故障演练。A6 继续维持约 98%，完成上述工作后进入 A6-8.2。

### A6-8.1 Redis 跨机器共享收口（2026-08-28）

- 新增 ADR-0017，保留 JSON 作为本地开发默认后端；配置 `TRAVEL_AGENT_PROVIDER_REDIS_URL` 后，高德和和风发布脚本显式切换到 Redis 共享后端，不在 Redis 故障时静默退回本机 JSON；
- 新增 `RedisProviderRequestGovernor`，通过 `WATCH/MULTI/EXEC` 乐观事务在多实例间共享按日安全预算、最小请求间隔、成功/失败计数、失败分类、连续失败和熔断状态；状态 TTL 为 90 天；
- 新增 `RedisGaodeRouteCache`，规范化路由键执行 SHA-256，值只保存模式、耗时、距离、抓取/过期时间并使用 Redis TTL；不同机器可复用成功路线，缓存命中不消耗 Provider 预算；
- `scripts/show_provider_governance.py` 自动识别 JSON 或 Redis，输出不包含 Redis URL、密码、API Key、专属 Host 或完整请求参数；
- 新增生产依赖 `redis>=4.6,<5`，保持与当前环境既有任务依赖兼容；测试新增 `fakeredis` 和 `types-redis`；
- fakeredis 双客户端共享治理/缓存单元测试通过；在用户明确“Redis/MySQL 服务不得在本机部署测试”边界前曾进行一次短生命周期本机 Redis 协议检查，随后验证键、临时进程和 `.local/redis-validation` 临时目录均已清理，系统既有认证 Redis 未读取密码、未写入数据；该本机检查不计入正式部署验收证据；
- 全量 pytest 由 272 增至 275 项通过；改动文件 Ruff、隔离 strict mypy 和 `git diff --check` 通过；求解器契约与 Gate 6 结果不变；
- 当前阶段结论：A6-8.1 持续服务治理代码闭环完成。正式环境仍需由用户提供服务器和授权 Redis URL，所有服务安装、TLS/ACL、集中配额看板、监控和多实例断连/恢复演练只在该服务器进行；本机仅保留不启动真实服务的纯单元/仿真测试。A6 仍维持约 98%，不代表 M1 MVP 完成。

### A6-8.2 服务器部署包与 SSH 接入准备（2026-08-28）

- 用户提供 `124.222.14.188`、`ubuntu`、sudo、新装 Redis/MySQL、同机 Docker Compose、允许恢复演练等部署边界；应用来源 IP/CIDR 尚未给出，因此 3306/6379 继续安全地只绑定服务器 `127.0.0.1`，不向公网开放；
- 新增 `deploy/production/`：MySQL 8.0、Redis 7.4 Alpine、独立数据/备份目录、服务健康检查、Docker 日志轮转、MySQL InnoDB/utf8mb4/UTC/慢查询配置、Redis AOF everysec/RDB/noeviction 和最小 ACL；
- 服务凭证只由服务器 `provision-secrets.sh` 使用 `openssl` 生成，不写入仓库或命令输出；MySQL 应用账号仅有 DML 权限，迁移账号与运行账号分离；Compose 不在 MySQL/Redis 容器之间交叉注入整套凭证；
- `backup.sh` 生成 MySQL gzip、Redis RDB 与 SHA-256；Redis BGSAVE 必须在 60 秒内产生新的成功快照，否则明确失败，不再复制旧 RDB；失败时清理 `.partial` 文件；
- 新增 `restore-drill.sh`，在一次性容器和一次性 Docker Volume 中校验哈希并隔离恢复 MySQL/Redis，检查 MySQL 表数量、Alembic revision 和 Redis 可读性，退出时删除演练资源，不覆盖生产数据目录；
- 仓库根 `id_rsa`/`id_rsa.pub` 与 PEM/PPK 已显式加入 Git ignore，两个根密钥文件均未被 Git 追踪；私钥只在 `.local/ssh/` 创建权限收紧的临时副本用于认证诊断；
- SSH 主机握手成功，服务器 ED25519 指纹已经通过 `accept-new` 写入本机 known_hosts；新私钥可以成功解析，其 RSA 公钥指纹为 `SHA256:OkMQtFzrvA8rCTOaZEO+jscyaPCikI+NtCmnJM9vTW4`，但服务器 `ubuntu` 返回 `Permission denied (publickey,password)`。工作区原 `id_rsa` 公钥属于另一密钥对，必须先把新私钥对应公钥加入 `/home/ubuntu/.ssh/authorized_keys`，不能从现有错误公钥推导；
- 未在本机启动 Redis/MySQL；当前全量 275 项测试再次通过，`git diff --check` 通过。服务器 `bash -n`、`docker compose config`、容量参数校准、真实部署、Alembic、ACL、并发、断连、备份恢复和监控证据尚未执行；
- 当前阶段结论：A6-8.2 已从“等待服务器信息”进入“部署包完成、等待 SSH 公钥授权”。该认证阻塞解除后，先执行只读资源/端口/防火墙盘点，再按实际内存与磁盘调整参数，之后才能部署，不能把本地静态准备标记为真实服务器验收完成。

### A6-8.2 真实 MySQL/Redis 部署与恢复验收完成（2026-08-28）

- 新私钥认证修复后完成 Ubuntu 24.04.4 服务器盘点：4 vCPU、约 3.6 GiB 内存、40 GiB 系统盘、Docker 29.1.3、Compose 2.40.3；发现同机已有两个 MySQL、一个 Redis 和一个 API 容器，因此不复用、不停止、不修改既有业务；
- 既有非本项目 MySQL 占用并向 `0.0.0.0` 暴露 3306，UFW inactive；Travel Agent 改用独立 Compose project/network/data，MySQL/Redis 只绑定 `127.0.0.1:13306/16379`。既有公网 3306 作为高风险遗留记录，未获授权不修改；
- 按同机资源将 MySQL 调整为 256 MiB buffer pool、50 最大连接、768 MiB 容器限制；Redis 调整为 128 MiB maxmemory、noeviction、192 MiB 容器限制；最终稳定观测约 371 MiB/3.3 MiB；
- MySQL 8.0.46 与 Redis 7.4 容器均 running/healthy；凭证只在服务器生成，`infra.env`/`app.env` 为 root 0600；MySQL 应用 DML、迁移 DDL、只读备份账号，以及 Redis 应用/备份管理员账号均已分离；
- MySQL 服务验证通过 InnoDB、utf8mb4、utf8mb4_0900_ai_ci、UTC、应用 DDL 拒绝和迁移 DDL 允许；Alembic 空库升级至 `0002_anonymous_identity (head)`；
- 真实 MySQL 验证通过中文、emoji、JSON、跨午夜、时区、重启读取、两连接 Intent 原子领取恰好一胜、事务异常回滚无残余；受控断连显式失败，重启后 `pool_pre_ping` 恢复且已提交数据存在；
- 真实 Redis 验证通过 10 连接并发计数、共享阈值熔断、`rate_limited` 立即熔断、跨客户端路线缓存、SHA-256 路线键、凭证/坐标不泄露；受控断连显式失败，重启后连接与 AOF/RDB 数据恢复；
- Redis 主机 `vm.overcommit_memory=1` 已持久化，重启后 overcommit 警告消失；真实 BGSAVE/备份再次通过；
- MySQL gzip 与 Redis RDB 备份、SHA-256、失败 partial 清理和 14 天保留已落地；隔离恢复得到 7 张 MySQL 表、Alembic 0002 和可加载 Redis RDB，演练临时容器/Volume 全部清理；
- `travel-agent-infra-backup.timer` 已 enabled/active，每日北京时间 03:30、随机延迟最多 15 分钟、错过后补跑；当前仍是同系统盘备份，没有异地副本；
- 服务器安装 `/opt/travel-agent/app` 与独立 Python venv，迁移和验收不把秘密复制回本机；`/etc/travel-agent/app.env` 只含应用账号连接，不含迁移账号；
- 根目录私钥继续由 `.gitignore` 显式排除且未被 Git 追踪；部署结束后本轮创建的两个 `.local/ssh` 私钥副本已删除，服务器 `/tmp` 暂存目录和归档也已清理；
- 全量本地 275 项测试、Ruff 和 `git diff --check` 保持通过；详细服务器证据见 `docs/test/reports/a6-8-2-server-mysql-redis-validation-2026-08-28.md`；
- 当前阶段结论：A6-8.2 的真实数据库/Redis/恢复范围完成。FastAPI/Taro 尚未作为公网生产服务发布，集中监控、异地备份、镜像 digest、Python 生产 lock、两台物理节点网络分区和 Gate 7 尚未完成；不能将 A6-8.2 完成扩大解释为 M1 MVP 或稳定生产完成。

### A6-8.2 提交边界整理（2026-08-28）

- 复核全部未跟踪文件：ADR、Provider 治理代码、单元测试、无凭证 Compose、备份/恢复和真实验收脚本均为可复现工程资产，必须提交，未通过 `.gitignore` 隐藏必要实现；
- 三个服务器专用 Python 验收脚本从根 `scripts/` 归并到 `deploy/production/validation/`，Shell wrapper 改为从自包含部署包调用；服务器新路径已重新执行 MySQL/Redis 验收，旧 `/opt/travel-agent/app/scripts/validate_*` 冗余副本已删除；
- 根 `.gitignore` 显式补齐 pytest/mypy/Ruff、coverage、Python build/dist、IDE/OS 临时文件、部署 `infra.env/app.env`、ACL、data、backup、SQL/RDB/AOF 等规则，不再依赖用户全局 ignore；
- `.env.example`、`deploy/production/infra.env.example` 和 `deploy/production/validation/*.py` 已确认仍可追踪；`.env`、`id_rsa`、`.local`、工具缓存和部署运行数据已确认命中 ignore；
- 整理后全量 275 项测试和部署 validation Ruff 通过，服务器 `bash -n`、Python `py_compile`、Compose config、真实 MySQL/Redis 验收通过，两个容器保持 healthy。

## 本轮完成（2026-08-24）

- 将产品路线术语从旧 `P1/P2/P3/P4` 统一迁移为 `M1/M2/M3/M4`；
- 明确 `P0/P1/P2` 仅表示实现优先级；
- 保留 `solver-p1-v1` 等历史兼容机器标识，避免破坏既有 Revision 回放；
- 完成 14 个 M1 功能模块的职责与优先级设计；
- 定义首个浏览器可用纵向切片和 M2–M4 功能归属；
- 建立本状态页，后续每轮任务结束必须同步更新。

### A1 专业化补充

- 将原“14 个模块概览”升级为三级功能架构；
- 一级功能域区分用户业务、数据运营、运营治理和平台支撑；
- 二级功能模块形成可映射页面、应用用例和服务边界的能力集合；
- 三级原子功能点补充里程碑、优先级、核心规则与验收口径；
- 明确首个纵向切片实际纳入和暂不纳入的三级功能；
- 建立 H1/H2/H3/H6/H7/H11 与功能点的追踪关系。

### A1 低操作负担重设计

- 将输入分为核心必填、推荐选择、高级调整、系统推导四类；
- 首次生成收敛为“什么时候去→想去哪里→确认并生成”三步；
- 杭州直接确认，旅行节奏默认适中，返程方式默认沿用到达方式，同行人群可跳过；
- 接驳、提前到站、末景返程由系统推导并集中显示摘要，不再要求用户逐项填写；
- 推导失败只追问缺失项，禁止静默使用 0；
- 增加生成前摘要、高级设置和结果页就地调整；
- 新增操作复杂度门禁：默认路径不超过 7 组输入、首次生成中位时间目标不超过 3 分钟、单项调整最多一次跳转；
- 算法权重、seed、硬约束开关等系统控制面不向普通用户暴露。

### A1 交通类型分类修订

- 到达交通类型与离开交通类型均调整为 R 类核心业务事实；
- 到达方式允许预选，但必须由用户选择或确认，不能静默假定高铁；
- 离开方式默认显式继承已确认的到达方式，大多数用户无需第二次选择；
- 新增 `unresolved/suggested/confirmed/confirmed_by_inheritance/overridden` 确认状态；
- 新增“已在目的地”选项，避免本地用户或提前抵达用户填写虚假交通方式；
- 交通方式保持业务必填，同时将大多数往返同方式用户的操作控制为 1 次。

### A2 信息架构与 UI 设计

- 首次生成固定为 P01“什么时候去”→P02“想去哪里”→P03“确认并生成”→P04“行程详情”；
- 定义 9 个前台页面和 6 个上下文面板，首个切片只实现 P0 页面；
- 匿名首版不设置多余底部 Tab，登录历史完成后再增加“规划行程/我的行程”；
- 到达方式采用快捷确认，离开方式采用显式继承，时间预留使用摘要 + 高级设置抽屉；
- 景点选择使用稳定列表、搜索筛选和底部已选栏，不制造推荐幻觉；
- 结果页先展示可执行时间线，再展示未排入、软降级和可信度说明；
- 定义 initial/restoring/ready/dirty/saving/validation_error/loading/empty/submitting/partial_success/soft_degraded/blocking_error/offline/expired 页面状态；
- 完成 P00/P01/P02/P03/P04、时间设置、未排入和反馈的低保真结构；
- 明确移动端、H5 和微信小程序的响应式、登录及分享差异。

### A3 交互流程与状态机

- 定义 IF-01–IF-12：首次生成、草稿、交通确认、景点选择、生成、未排入、高级设置、修订、登录绑定、反馈、分享和异常恢复；
- 完成首次生成的用户/UI/应用服务/求解器时序；
- 完成草稿、到达/离开交通、景点选择和生成状态机；
- 明确返回不丢数据、自动保存、草稿冲突和本地离线恢复；
- 定义 `generation_intent_id` 语义，双击和网络重发复用同一生成意图；
- 区分系统稳定重试、用户修改后重新生成和未来受控“换一个方案”；
- 完整成功、部分成功、软降级、无解、超时无解和无效输入分流明确；
- 未排入原因映射到调整日期、锚点、节奏、景点或稳定重试；
- 登录失败不清除匿名行程，绑定行程需要显式确认和幂等；
- 定义离线、匿名过期和草稿期间数据版本变化的恢复策略；
- 增加正常路径、交通继承、重复点击、部分成功和数据变化的 Given/When/Then 场景。

### 产品功能完整性复审

- 确认景点评分与讨论区属于 M3，原功能树只做路线占位、未形成可实现功能模块；
- 新增“景点评分、讨论与内容治理”功能域，补齐评分上下文、Tips/时效/避坑内容、点赞、排序、置顶、举报、审核和反垃圾；
- 将 M2 旅行小记从旧“仅按日期组织”细化为“具体行程节点优先、日期级回退”；
- 新增行程开始/继续/结束，以及节点到达、完成、跳过和纠正等实际执行状态；
- 补齐图片上传、压缩、失败恢复、排序、封面、EXIF/位置隐私和内容删除边界；
- 区分 M1 计划分享、M2 旅程回顾分享和 M4 自动图文游记，禁止用同一“行程分享”语义混用；
- 旅程回顾支持用户选择部分节点小记和照片，未选择的私密内容不得自动公开；
- 将全路线功能架构由 9 个 M1 中心功能域扩展为 14 个跨里程碑功能域；
- 补齐灵感、深度信息、决策辅助、住宿餐饮交通、预订、自驾、行前行中、协同、旅行档案、长期偏好和用户共创等原遗漏功能族；
- 记录历史产品文档中的体力硬预算、室内自动替代、阶段术语和假设里程碑冲突，后续按 Accepted ADR/规格优先处理；
- A2/A3 仍保持 M1 范围，但已登记 M2–M4 必须新增的页面和交互流程，避免误把计划分享复用为回顾分享。

### A2.1/A3.1 跨里程碑同步修订

- A2 升级至 V1.1，保留 M1 三步主流程和原页面职责；
- 将行程详情明确拆为 planning、in_trip、review 三种业务模式，模式不由日期或路由猜测；
- 登记 P10–P32 后续前台页面族与 O10–O14 内容治理后台页面族；
- 明确开始行程、当前节点、快速小记、旅程回顾、景点讨论和审核后台的入口与深化时机；
- 新增执行、小记、媒体、授权、回顾、社区和治理组件边界；
- A3 升级至 V1.1，登记 IF-13–IF-24；
- 完成 TripExecution 生命周期和 Visit 到达/完成/跳过/纠正核心状态机；
- 完成小记私密保存、节点优先/日期回退、媒体失败恢复和内容复用授权规则；
- 完成计划分享、旅程回顾、自动游记三类发布流程和幂等语义分离；
- M2–M4 仅同步架构边界，详细低保真、异常时序和验收场景仍在进入对应里程碑时完成；
- M1 首个纵向切片未扩大，可继续进入 A4。

### A4 应用代码架构设计

- 选择单体部署、模块化边界，不提前拆微服务；
- 明确 domain → application → interfaces/infrastructure 的依赖方向和组合根；
- 将 Planning、Catalog、Feedback、Identity、Sharing 与未来 Execution、Journal、Community、Retrospective 分界；
- 定义 TripDraft、Trip、TripRevision、GenerationIntent、SolverRun 的关系和不变量；
- 将 SubmitGeneration 与 ExecuteGeneration 分离，求解期间不持有数据库事务；
- 通过 SolverGateway 隔离应用 DTO 与 `travel_agent.solver` 纯模型；
- 通过 GenerationExecutor 隔离 inline 和后续 Celery，首切片不强制 Redis/WebSocket；
- 定义 draft_version 乐观锁、intent 唯一键、input snapshot hash 和执行原子领取；
- 定义运行日志、求解决策审计、业务修订和数据发布审计的边界；
- 定义 Taro 前端 feature/page/shared 分层及服务端、草稿、页面瞬时状态归属；
- 定义求解器、领域、应用、适配器、API、纵向切片和 Gate 6 的测试层级；
- 标记旧 API 与数据模型中的 regenerate、单 itinerary JSON、单 transport_type、默认 Celery/WebSocket 等 A5 必修项；
- 明确首个切片实现顺序，不包含登录、分享、在线 Provider、小记或社区。

### A5 API 与持久化数据模型同步

- 将旧 API 契约升级为 V2.0，统一使用 `/api/v1`；
- 新增匿名会话、草稿、旅行事实、景点选择、生成前 review、GenerationIntent、Trip 和不可变 Revision 资源；
- 取消含义混乱的 `/regenerate`，区分稳定重试、修改后生成和未来替代方案；
- 到达/离开交通类型、确认状态和时间预留分别建模；
- 定义 queued/running/completed/failed_retryable/failed_terminal 应用状态，并与求解搜索状态分离；
- 将完成范围和软降级拆为正交维度：complete/partial + has_soft_degradation，支持“部分成功且同时软降级”；
- 完整设计 provenance、accounting、timeline、unplaced、data_rejected 和 degradations 响应；
- 定义 HTTP 错误码、求解拒绝码分层、匿名权限和轮询规则；
- 数据模型升级为 principals、trip_drafts、generation_intents、solver_runs、trips、trip_revisions 等结构；
- 使用 draft_version 乐观锁、intent 主键和 input hash、执行条件更新、revision/run 唯一约束保护并发；
- 多开放规则、多闭馆日、具体日期例外、天气和有向 OD 形成可发布数据快照；
- 输入/结果 snapshot 保存 Schema 版本和稳定哈希，历史 Revision 不可原地覆盖；
- 定义求解完成短事务、失败恢复、数据保留和 Alembic 001–010 迁移顺序；
- 补充 8 个 API 验收场景和 6 个数据模型验收场景；
- A5 未扩大 M1 范围，M2–M4 仍未创建空表。

### A6-1/A6-2 应用核心实现

- 新增 `domain/planning`，实现 TransportType、ConfirmationStatus、TravelFacts、TripDraft 和 GenerationIntent；
- 到达交通禁止继承，离开继承必须与到达方式一致，非“已在目的地”的进城接驳不能为 0；
- TripDraft 使用不可变数据类和单调递增 `draft_version`，景点选择/偏好稳定排序；
- 新增稳定应用错误：resource_not_found、draft_version_conflict、generation_intent_conflict、draft_not_ready；
- 新增 Clock、UnitOfWork、ID、数据快照版本和 GenerationExecutor 端口；
- 实现 CreateDraft、UpdateTravelFacts、ReplaceAttractionSelection、SubmitGeneration 用例；
- SubmitGeneration 先按 intent ID 查重，重复提交不重新选数据版本、不重复调用执行器；
- 首次 intent 固化规范化输入 JSON、SHA-256 hash、数据版本和确定性内部 seed；
- 新增事务型内存 Unit of Work，未 commit 或异常时丢弃工作副本；
- 新增 7 项应用测试，覆盖版本冲突、选择规范化、幂等双击、intent 冲突、未就绪草稿和越权隐藏；
- 全量测试由 154 增至 161 项通过；
- 当前尚未实现 SolverGateway、Trip/Revision 完成结果、SQLAlchemy、HTTP 或前端。

### A6-3 生成执行应用闭环

- 新增 Trip、不可变 TripRevision、SolverRun 领域记录，以及 complete/partial 与软降级正交表达；
- GenerationIntent 增加 queued/failed_retryable → running 的原子领取语义，以及 completed、failed_retryable、failed_terminal 状态转换；
- UnitOfWork 增加 Trip、TripRevision、SolverRun 仓储边界，内存事务同步支持全量回滚；
- 定义 SolverRequest、SolverOutcome、SolverGateway 和可重试/终止 SolverExecutionError；
- 实现 ExecuteGeneration：领取事务、事务外求解、完成事务三段分离，求解期间不持有事务；
- 质量门通过时原子写入 SolverRun、Trip、Revision 并完成 Intent；
- 质量门失败只保留失败 SolverRun，不生成可展示 Revision；求解异常按可重试性更新 Intent；
- completed Intent 重复消费直接复用原 Trip/Revision，不重复调用求解器；running Intent 拒绝第二执行者领取；
- 新增 6 项应用测试，覆盖成功闭环、partial+soft degradation、重复消费、并发领取、质量门失败和错误分类；
- 全量测试由 161 增至 167 项通过；
- 本切片完成应用执行骨架，下一步接入现有纯求解器的生产 SolverGateway 适配器与稳定结果映射。

### A6-4 生产 SolverGateway 与稳定结果映射

- 新增版本化 PublishedSolverData、PublishedAttraction 和数据提供器边界；内存 Provider 仅用于当前集成测试，不替代生产数据库；
- ProductionSolverGateway 已把 generation-input-v1 转换为日期、时间锚点、旅行节奏、景点和时段偏好求解输入；
- 串联 assign_days、route_itinerary、质量门、降级评估和求解决策审计，继续使用冻结 solver/constraint/parameter 版本；
- SolverRun ID 在求解前生成并传入网关，审计 payload 与最终持久化 SolverRun 使用同一身份；
- 输入执行前重新计算 SHA-256，发现快照被篡改时以 invalid_solver_input 终止，禁止在不一致输入上回放；
- 区分发布快照缺失的可重试失败与景点引用、Schema、城市、版本等无效输入的终止失败；
- 新增 trip-result-v1 映射：provenance、summary、accounting、每日天气/时间线/交通/用餐、时段偏好、未排入、数据拒绝、跨天重分配和降级；
- 结果使用外部景点 ID，不向应用/API 暴露求解器内部整数 ID；
- node_id 由 intent、日期、景点和 occurrence 确定性生成，刷新和稳定回放不会变化；
- 新增 4 项网关集成测试，覆盖真实求解闭环、稳定结果哈希与节点 ID、审计身份、快照缺失、未知景点和哈希完整性；
- 全量测试由 167 增至 171 项通过；原 154 项 Gate 6 求解器基线保持通过；
- 下一步进入真实 SQLAlchemy 持久化，之后再建设 HTTP v1 和前端页面。

### A6-5 SQLAlchemy 持久化与 Alembic 迁移

- 将 SQLAlchemy 2.x 与 Alembic 1.x 加入正式生产依赖范围；当前环境已有兼容版本，无需额外联网下载；
- 新增 Planning 显式 ORM 行模型，领域与应用层仍不依赖 SQLAlchemy；
- 实现 TripDraft、GenerationIntent、Trip、TripRevision、SolverRun 的双向显式 Mapper；
- 时间戳以带偏移的 ISO-8601 字符串保存，避免 SQLite 丢失时区语义；输入、结果和审计继续使用不可变语义的 JSON 快照；
- 实现 SqlAlchemyUnitOfWork 及五类仓储，事务退出或异常时回滚，commit 后才对其他会话可见；
- 草稿更新使用 draft_id + expected draft_version 条件更新，冲突返回现有 DraftVersionConflictError；
- Intent 更新使用 intent_id + expected status 比较交换，只有一个执行者能从 queued 状态成功领取；
- TripRevision 对 generation_intent_id 唯一，SolverRun 对 generation_intent_id 唯一，防止同一生成意图产生重复正式结果；
- 新增 Alembic 环境和 0001_planning_core 初始迁移，可从空 SQLite 数据库创建当前 Planning 核心表和索引；
- 新增 6 项数据库测试：跨 Engine 恢复、草稿乐观锁、Intent 单次领取、异常回滚、ExecuteGeneration 完整图持久化、Alembic 空库升级后读写；
- 全量测试由 171 增至 177 项通过；原 154 项 Gate 6 求解器基线保持通过；
- 当前迁移只覆盖首个纵向切片的 Planning 核心，不提前创建 M2–M4 空表；匿名 principal/session、HTTP 和组合根进入 A6-6。

### A6-6 匿名身份与 FastAPI HTTP v1

- 将 FastAPI、uvicorn 纳入生产依赖，httpx 纳入开发测试依赖；当前环境已有兼容版本，无需额外联网下载；
- 新增匿名凭证表和 Alembic 0002 迁移，客户端只收到一次原 token，数据库仅保存 SHA-256 摘要和过期时间；
- 匿名请求使用 Authorization Bearer token；Draft、Intent、Trip、Revision 均按 principal 校验，越权与不存在统一返回 404；
- 实现 health/live 与 health/ready，readiness 当前验证数据库连接；迁移版本和发布数据 readiness 后续继续增强；
- 实现草稿创建/恢复、旅行事实更新、景点选择替换、生成前 review、GenerationIntent 提交/查询、Trip 与 Revision 查询；
- 实现景点列表和详情入口，响应使用发布数据快照版本与外部景点 ID，不暴露求解器内部整数 ID；
- 新增 InlineGenerationExecutor，将 HTTP 提交连接到现有 ExecuteGenerationHandler；首切片同步执行但保持可替换 Executor 端口；
- 新增生产组合根：数据库 Engine/Session、SQL UOW、UUID 不透明 ID、匿名身份、ProductionSolverGateway 和 inline executor；
- 所有响应附带 X-Request-ID；ApplicationError、401、Pydantic 422 与领域校验统一返回版本化错误结构，不返回堆栈、SQL 或 token；
- 草稿响应按 API 契约输出 city、arrival、departure、节奏、同行人群、选择和 last_saved_at，不直接泄漏领域 dataclass 结构；
- 新增 6 项 HTTP 测试，覆盖完整匿名规划闭环、跨主体资源隐藏、版本冲突、认证/字段错误、领域校验、readiness 和发布景点目录；
- 全量测试由 177 增至 183 项通过；原 154 项 Gate 6 求解器基线保持通过；
- 当前已经形成后端 HTTP 可调用闭环，但正式发布数据仍为内存 Provider，尚未经过 MySQL 方言验证，也尚无前端页面。

### A6-6.5 MySQL 方言与部署准备

- 增加 PyMySQL 生产依赖并安装 1.2.0；修复提升权限安装造成的单一包目录读取权限后，当前项目 Python 可正常导入；
- 新增 DatabaseSettings.from_env，数据库 URL 标记为不参与 repr，避免配置对象打印明文密码；
- 增加 pool_pre_ping、pool_size、max_overflow、pool_recycle、pool_timeout 配置；MySQL 使用 READ COMMITTED 与 utf8mb4；
- Alembic env 支持 TRAVEL_AGENT_DATABASE_URL 覆盖本地 URL，生产凭证无需写入 alembic.ini；
- 全部 ORM 表与 0001/0002 迁移声明 InnoDB、utf8mb4、utf8mb4_0900_ai_ci；
- 新增 DatabaseReadiness，区分数据库可连接与 Alembic revision 达标，当前期望 revision 为 0002_anonymous_identity；
- `/health/ready` 的生产组合根现在检查数据库和迁移两个维度，而不只执行 SELECT 1；
- 新增 3 项兼容测试：环境变量/密码隐藏、MySQL+PyMySQL Engine 与全表 DDL 编译、迁移 readiness 前后状态；
- MySQL DDL 已验证包含 InnoDB、utf8mb4、utf8mb4_0900_ai_ci 和 JSON；全量测试由 183 增至 186 项；
- 新增 docs/ops/mysql-deployment.md，记录版本、网络、最小权限、配置、迁移、并发、备份和恢复清单；
- 根据用户 2026-08-28 的环境边界，本机禁止安装、启动或部署测试 MySQL/MariaDB/Redis；真实 InnoDB 双连接并发、服务器 TLS、备份和故障恢复必须在用户提供并授权的服务器上验证，当前不标记为生产 MySQL 已完成。

### A6-7 Taro/React 前端首轮实现

- 新建 frontend/，采用架构文档确定的 Taro 4.2.1 + React 18 + TypeScript + Zustand，不改为仅 H5 的临时 React 项目；
- 建立 P00 首页、P01 时间与交通、P02 景点选择、P03 确认生成、P04 行程详情五个首切片页面；
- P00 自动创建匿名会话和草稿，并使用本地持久化恢复 token、draft、选择及 Trip/Revision 引用；
- P01 支持日期、到达方式、开始/到达时间、返程继承和结束/离开时间；默认路径使用系统时间预留，不暴露 seed 或求解权重；
- P02 从发布景点 API 加载列表，支持搜索、室内筛选、明确选中状态和底部已选数量；不显示虚构评分或 AI 推荐理由；
- P03 调用 review，展示日期、到离、节奏、已选数量和系统考虑项，并通过 GenerationIntent 生成行程；
- P04 按服务端顺序展示日期 Tab、天气依据、时间线、交通、晚餐、未排入、软降级和数据来源，不在前端重新排序或计算 C1–C6；
- 建立共享 API 错误、Planning 类型、Zustand 跨页状态、StepHeader 和唯一主操作按钮组件；
- 完成 375px 移动端优先样式，并为桌面宽度保留最大阅读宽度；状态不只依赖颜色，选中、未排入和降级均有文字；
- H5 开发配置将 /api 和 /health 代理到本地 FastAPI 8000 端口；微信小程序构建入口也已登记；
- 隔离安装并校验 Node.js 22.23.2/npm 10.9.8，使用 `.nvmrc`、`engines`、`packageManager` 和 package-lock 固定当前可重复构建基线；
- 补齐 Taro Router、Babel TypeScript preset、React preset、Fast Refresh 与 SWC Windows 原生绑定等直接依赖，修复 TypeScript/webpack alias 不一致；
- `npm ci` 已从 lockfile 干净安装 1235 个包，TypeScript `tsc --noEmit` 和 H5 production build 均通过；当前仅有 app 入口约 303 KiB 的性能警告，不阻塞纵向切片；
- 新增 SQLite + Alembic + FastAPI + ProductionSolverGateway 本地启动入口，以及 7 个明确标注为 local fixture 的杭州景点、动态日期天气和近似 OD 快照；
- 新增 2 项本地组合测试，全量由 186 增至 188 项通过；真实运行进程完成匿名会话→草稿→旅行事实→7 景点→review→Intent→Revision，结果为 complete_success、7/7 排入、晚间灯光秀成功排入；
- 浏览器控制运行时当前没有可用浏览器实例，因此没有完成可见页面点击、375px/桌面截图、刷新恢复和 UI 错误状态验证；A6-7 继续标记为进行中，不宣称普通用户已稳定可用。

## 后续队列

### 本轮更新（2026-08-30，O05 只读时间证据）

- 当前里程碑：M1；当前 Gate：G7 / R0.2-05-02 OM1 O05 地点审核工作台。
- 本轮完成：Revision evidence 装配 `PlaceTimeRule`、`PlaceClosure`、`PlaceDateException`；来源依赖闭包和逐项 `source_record_valid` 同步覆盖三类时间证据；admin-web 新增独立 O05 只读卡片并明确跨午夜“次日”语义。
- 边界：本切片不提供时间证据写入、逐项审核或指定日期解析预览；O04 与 O05 各自独立降级，证据服务异常不会清空 O03 基础事实和审核操作。
- 验证结果：完整后端测试 351/351 通过；admin-web typecheck、Vitest 7/7、production build通过；相关 Python Ruff 和 `git diff --check` 通过。
- Chrome 验收：从 72 条候选清单进入“西湖音乐喷泉表演” Revision，O05 卡片、三类空状态、O03/O04/O05 分区和更新后的边界文案均符合预期，控制台新增 warn/error 为 0；未通过 SQL 手工制造时间数据。详见 `docs/test/reports/g7-r0.2-05-02-o05-time-evidence-chrome-2026-08-30.md`。
- 当前进度：O04 已提交；O05 只读时间证据纵向切片已完成并达到可提交状态。
- 遗留问题：O05 CRUD/逐项审核/解析预览，O01、O06、O07、发布中心和批量审核仍属于后续节点；SQLite datetime adapter 警告和全仓历史 Ruff 不属于本轮阻断。
- 下一步：提交 `feat(admin): expose revision time evidence`；随后进入 O05 时间证据写入与 reviewer 审核闭环。

| 顺序 | 阶段 | 内容 | 当前状态 |
|---|---|---|---|
| 1 | A1 | 功能模块设计 | 已完成 |
| 2 | A2 | 信息架构、页面清单与 UI 设计 | 已完成 |
| 3 | A3 | 核心交互流程、页面状态与异常流程 | 已完成 |
| 3.5 | 产品功能完整性复审 | 全景需求追踪、缺口补齐与冲突登记 | 已完成 |
| 3.6 | A2.1/A3.1 | 全路线 UI/交互边界同步 | 已完成 |
| 3.7 | OM1–OM4 管理端产品设计 | 管理功能、页面、流程、架构、API 和逻辑数据模型 | 设计完成；身份/API/审计后端、admin-web 壳与地点审核工作台首版已实现，O04 几何/访问点写入与逐项 reviewer 审核闭环已完成，发布中心待实现 |
| 4 | A4 | 应用代码架构、模块边界与依赖规则 | 已完成 |
| 5 | A5 | API 与持久化数据模型同步 | 已完成 |
| 6 | A6 | 首个浏览器可操作纵向切片 | 已完成（100% 仅指技术纵向切片；替换、我的行程、计划分享、结构化反馈均通过 Chrome 验收） |
| 7 | G7 | 真实专家评审与用户验证 | R0.2-01～04、05-01A、05-01B 已完成；当前 05-02。O04 写入审核已完成，正在推进 O05；后续完成 O01/O05–O07、批量审核、OD、发布、R0.3 部署、R0.4 dry run、招募和真实证据 |

## 首个可用目标

```text
打开浏览器
→ 确认杭州，选择旅行日期与到达/离开时间
→ 选择或确认到达交通方式；返程方式默认显式继承
→ 系统自动预留进城接驳、提前到站和末景返程时间，用户可按需调整
→ 浏览并勾选景点
→ 确认摘要，默认使用“适中”节奏；同行人群与高级设置可选
→ 生成行程
→ 查看每日时间线、交通、晚餐、天气、时段偏好、未排入项与降级原因
→ 按需替换单个景点并生成同一 Trip 的新 Revision，旧版本继续保留
→ 从“我的行程”恢复当前版本，并可只读回看历史 Revision
→ 将当前 Revision 生成为脱敏计划分享，访客可只读查看或复制景点为自己的新草稿
→ 保存本次结果并提交结构化整体/节点反馈
```

## 明确未完成

- FastAPI HTTP v1、匿名会话和组合根已完成首切片；真实 MySQL 已部署并通过持久化/恢复验收，但 FastAPI/Taro 尚未作为外网生产服务启动，域名/TLS、反向代理和应用进程安全加固仍未完成；
- Planning SQLAlchemy 仓储与迁移已完成；正式不可变 JSON PublishedDataProvider 已接入生产组合根并完成回放，但正式发布数据尚未迁入数据库发布表；
- Alembic 0003/0004/0005/0006 已在本地升级和自动化测试通过，但服务器真实 MySQL 仍是已验收的 0002 基线；下一次应用发布前必须以迁移账号依次执行 0003、0004、0005、0006，并重新验证 readiness、备份与隔离恢复；OM1 后续表尚无迁移，不能提前假定迁移编号；
- 高德真实路网和和风真实三日天气均已完成严格快照、正式 bundle、Gateway 消费和生产回放；Redis 真实 ACL、并发治理、熔断、路线缓存、断连恢复和备份已通过，尚未完成正式配额来源/集中看板、两台物理节点网络分区、跨主机 TLS和三日之外的正式气候基线；登录等其他真实外部 Provider 尚未接入；
- 午晚餐当前仍是软留白；具体餐厅节点、餐厅加入后的真实 OD 完整重排和新 Revision 流程尚未实现；
- Taro/React P00–P08、景点替换页、依赖锁定、TypeScript、H5 production build 已完成；P00–P08 和替换/历史/分享页面的 Google Chrome 移动端/桌面端门禁已通过；多浏览器、弱网、长时会话和生产部署验证尚未完成；
- A6 已有领域/应用、求解器、真实 MySQL/Redis、HTTP API、前端页面、真实高德/和风、正式 JSON 发布数据、本地生产 Chrome、断连和备份恢复闭环；由于 M1 产品缺口、外网应用服务、集中监控、异地备份和 Gate 7 仍未完成，仍不能宣称普通用户可稳定生产使用；
- 全项目严格 Mypy 基线尚未清零；当前本轮新增文件在隔离导入检查下通过，最近完整基线仍为 154 条/27 个历史文件，需另立技术债切片处理；
- 计划分享安全链接与 HTML/CSS 模板卡首版已实现；PNG/JPEG 导出、二维码/小程序码、保存相册、原生平台分享、作者撤回和转化埋点尚未实现；
- “我的行程”匿名主体列表、最新 Revision 恢复和历史修订查看已实现；账号行程、草稿/失败 Intent 并入列表仍待登录与恢复切片；
- M2 节点旅行小记、媒体和旅程回顾仅完成产品设计，尚未实现；
- M3 景点评分、讨论区、内容治理和行中动态服务仅完成产品功能骨架，尚未进入详细 PRD 或实现；
- M4 自动游记、旅行档案和长期偏好仅完成产品功能骨架，尚未进入详细 PRD 或实现；
- OM1–OM4 管理侧路线、OM1 P0 功能/UI/交互/API/数据逻辑设计已完成；OM1 管理身份、RBAC、管理审计以及 O00/O15/O16、O02/O03/O04 admin-web 安全操作面已实现，O04 几何/访问点 candidate 写入、编辑、软停用和逐项 reviewer approve/reject 已完成；O01/O05–O07 和发布中心仍未实现；
- Gate 7 R0.1 研究环境锁定机制、R0.2-01 地点/投影 ADR、R0.2-02 来源治理、R0.2-03 通用地点物理模型/发布门禁和 R0.2-05-01B 管理 Web 安全操作面已完成；R0.2-05-02 中 O04 Geometry/AccessPoint 写入与逐项审核已完成。杭州批量 human_verified、O05–O07、按需 OD 子图、服务器数据库迁移、H5/admin-web/HTTPS 正式部署、内部 dry run 和首个 locked manifest 尚未实现，外部专家/用户证据、H3 结论和 M1 MVP 均未完成。

## 每轮结束更新模板

```text
更新时间：YYYY-MM-DD
产品里程碑：M-x
当前阶段：A-x / G-x
本轮完成：
- ...
验证结果：
- ...
当前进度：
- ...
遗留问题：
- ...
下一步：
- ...
```

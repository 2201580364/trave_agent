# 项目状态与续接记录

> 本文件是每次任务结束时必须更新的统一状态入口。新会话先读本文件，再按“下一步”继续。

## 术语

| 术语 | 含义 |
|---|---|
| `M1–M4` | 产品路线里程碑；M1 是最小可用产品，M2 是信息与决策增强，M3 是全流程出行服务，M4 是记忆与生态 |
| `P0` | 当前里程碑的阻塞优先级；缺失时无法形成首个可用闭环或无法验证核心假设 |
| `P1` | 当前里程碑的重要优先级；MVP 应具备，但可以晚于首个纵向切片 |
| `P2` | 增强优先级；不阻塞当前里程碑，可在证据充分后实现 |
| `G0–G7` | 假设驱动开发的证据 Gate，不等同于产品路线或实现优先级 |

历史机器标识 `solver-p1-v1`、`parameters-p1-*` 和 `DEFAULT_SOLVER_P1_CONTRACT` 已被冻结，仅作为兼容性 ID 保留；其中的 `p1/P1` 不再表示产品阶段命名。

## 当前总状态

- 更新时间：2026-08-24
- 产品里程碑：`M1 — 行程骨架验证`
- 证据 Gate：Gate 6 求解器技术验证已通过；Gate 7 专家/用户验证尚未开始
- 当前阶段：`A6 首个浏览器纵向切片实现中；A6-1 至 A6-5 已完成，下一步 A6-6 HTTP v1`
- 当前任务：Planning 核心已具备 SQLAlchemy 持久化、Alembic 初始迁移、乐观锁、Intent 条件领取与数据库恢复；准备建设 API 入口
- 总体判断：求解器已经可被应用层依赖，但产品尚无 UI、HTTP 入口、数据库或用户可操作闭环

## 已完成

| 工作流 | 状态 | 证据 |
|---|---|---|
| G3 求解器 Spike | 完成 | `spike/` 历史证据 |
| G4 求解器设计与约束分级 | 完成 | ADR-0003/0004 |
| G5 C1/C2/C4/C5/C6 与分层求解 | 阶段性完成 | 核心能力已通过 Gate 6；后续可根据应用集成、真实数据和用户验证继续修复或演进 |
| 日志与审计 | 完成 | 模块级、按级别每日文件、月度压缩归档 |
| Gate 6 Golden/降级/性能/接近度 | 通过 | `docs/test/reports/` |
| M1 求解器契约冻结 | 完成 | ADR-0009、`solver-p1-v1` 机器快照 |
| A1 功能模块设计 | 完成（V3.0） | 14 个跨里程碑一级功能域；M1 详细功能树保持稳定，M2–M4 补齐可追踪功能骨架，见 `docs/product/功能模块设计.md` |
| 产品功能完整性复审 | 完成（V1.0） | 产品全景→功能树追踪、遗漏项、用户新增细化和历史规格冲突，见 `docs/product/产品功能完整性审查.md` |
| A2 信息架构与 UI 设计 | M1 详细设计完成；全路线同步完成（V1.1） | 保留 M1 页面和关键低保真；补充规划/行中/回顾三模式、M2–M4 页面族、入口与组件边界，见 `docs/product/信息架构与UI设计.md` |
| A3 交互流程与状态机 | M1 详细设计完成；全路线同步完成（V1.1） | IF-01–IF-12 可进入实现；登记 IF-13–IF-24，并明确执行、Visit、小记、媒体、授权和回顾状态，见 `docs/product/交互流程与状态机设计.md` |
| A4 应用代码架构设计 | 完成（V1.0） | 模块化单体、分层依赖、应用用例、求解器网关、事务幂等、前端目录、测试架构与纵向切片，见 `docs/product/应用代码架构设计.md` |

最新稳定技术基线：全量 177 项测试通过，其中 Gate 6 求解器基线 154 项保持通过；Golden 6/6；降级 8/8；杭州公开攻略综合接近度 0.975。该证据只证明技术可行性，不证明 H3 已被专家或用户证实。

状态口径：求解器**核心实现已阶段性完成**，不是永久冻结；被冻结的是 M1 对外契约、约束语义和默认参数版本。允许继续进行缺陷修复、内部重构、性能优化和基于真实验证的后续演进，但契约行为变化必须按 ADR-0009 评审并升级相应版本。

## 正在进行

### A4：应用代码架构设计

- 状态：已完成
- 核心产物：`docs/product/应用代码架构设计.md`
- 关键结论：模块化单体；首切片 inline executor；通过 GenerationExecutor 可替换 Celery；Trip/Revision/Intent/SolverRun 分离；SolverGateway 隔离冻结求解器；M2–M4 只保留边界、不创建空模块
- 完成度：100%

### A5：API 与持久化数据模型同步

- 状态：已完成
- 核心产物：`docs/specs/api-contract.md` V2.0、`docs/specs/data-model.md` V2.0
- 关键结论：草稿/Intent/Trip/Revision 资源分离；无 `/regenerate`；到离交通事实分离；输入/结果 snapshot 版本化；草稿乐观锁、intent 原子领取、Revision/SolverRun 原子完成事务明确
- 完成度：100%

### A6：首个浏览器可操作纵向切片

- 状态：进行中
- 当前输入：A4 架构、A5 HTTP v1 契约与数据库模型、冻结求解器契约
- 首个实现切片：匿名会话 → 草稿 → 杭州景点 → GenerationIntent → inline SolverGateway → TripRevision → 恢复结果
- 已完成：A6-1 领域/应用基础；A6-2 草稿与提交；A6-3 执行事务；A6-4 求解适配；A6-5 SQLAlchemy 持久化
- 下一步：A6-6 FastAPI 应用入口、匿名会话最小身份、HTTP v1 Schema/路由/错误映射和 inline 组合根
- 完成度：约 55%（仅指首个纵向切片，不代表 M1 MVP）

## 本轮完成（2026-08-24）

- 将产品路线术语从旧 `P1/P2/P3/P4` 统一迁移为 `M1/M2/M3/M4`；
- 明确 `P0/P1/P2` 仅表示实现优先级；
- 保留 `solver-p1-v1` 等冻结机器标识，避免破坏契约兼容性；
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

## 后续队列

| 顺序 | 阶段 | 内容 | 当前状态 |
|---|---|---|---|
| 1 | A1 | 功能模块设计 | 已完成 |
| 2 | A2 | 信息架构、页面清单与 UI 设计 | 已完成 |
| 3 | A3 | 核心交互流程、页面状态与异常流程 | 已完成 |
| 3.5 | 产品功能完整性复审 | 全景需求追踪、缺口补齐与冲突登记 | 已完成 |
| 3.6 | A2.1/A3.1 | 全路线 UI/交互边界同步 | 已完成 |
| 4 | A4 | 应用代码架构、模块边界与依赖规则 | 已完成 |
| 5 | A5 | API 与持久化数据模型同步 | 已完成 |
| 6 | A6 | 首个浏览器可操作纵向切片 | 进行中（约 55%） |
| 7 | G7 | 真实专家评审与用户验证 | 未开始 |

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
→ 保存本次结果并提交反馈
```

## 明确未完成

- FastAPI 应用、HTTP 路由、匿名会话与组合根尚未实现；
- Planning SQLAlchemy 仓储与初始迁移已完成；发布数据 Provider 仍为内存测试适配器，正式数据发布表尚未接入；
- 地图、天气、登录等真实外部 Provider 尚未接入；
- Taro/React 前端与任何页面尚未实现；
- A6 已有领域/应用核心、生成执行事务、生产求解器适配器和 Planning 数据库持久化，尚无 HTTP 用户入口与前端；
- 分享卡片尚未实现；
- M2 节点旅行小记、媒体和旅程回顾仅完成产品设计，尚未实现；
- M3 景点评分、讨论区、内容治理和行中动态服务仅完成产品功能骨架，尚未进入详细 PRD 或实现；
- M4 自动游记、旅行档案和长期偏好仅完成产品功能骨架，尚未进入详细 PRD 或实现；
- Gate 7、H3、M1 MVP 均未完成。

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

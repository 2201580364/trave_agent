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

历史机器标识 `solver-p1-v1`、`parameters-p1-*` 和 `DEFAULT_SOLVER_P1_CONTRACT` 必须保留；其中的 `p1/P1` 不再表示产品阶段命名。当前结构契约已按 ADR-0011 升级为 `solver-p1-v2 / trip-result-v2`；参数按 ADR-0013 保持 `parameters-p1-2026-08-26`，单日间节点下午展开语义按 ADR-0015 升级为 `constraints-p1-v5`；历史版本仅用于不可变 Revision 回放。

## 当前总状态

- 更新时间：2026-08-27
- 产品里程碑：`M1 — 行程骨架验证`
- 证据 Gate：Gate 6 求解器技术验证已通过；Gate 7 专家/用户验证尚未开始
- 当前阶段：`A6-8.1 配额与快照持续服务收口：路线点、严格 OD、下午展开、真实和风天气、正式 Published Snapshot 和生产 FastAPI/Chrome 回放已完成`
- 当前任务：补齐和风/高德配额看板、限流、熔断、跨机器缓存与旧快照继续服务策略；随后进入 A6-8.2 真实 MySQL 与部署恢复
- 总体判断：后端 HTTP、配置数据库持久化、前端五页面、H5 production build、Chrome 真实浏览器门禁、日内节奏修订、高德真实 Provider 和和风真实三日预报已形成可操作技术纵向闭环；7 个杭州路线点已经发布责任人接受并生成独立 `human_verified` 坐标版本，新版本 42/42 有向 OD 均来自高德且 0 fallback/0 missing，历史候选数据未覆盖。新 OD 暴露的 5 小时 22 分钟下午空白已经通过 ADR-0015 和 `constraints-p1-v5` 收口。和风认证按官方专属 Host + `X-QW-Api-Key` 请求头完成真实验证，已生成 2026-08-27 至 2026-08-29 的不可变天气快照和正式杭州 Published Solver Snapshot，并通过生产组合根、FastAPI 端到端生成、Revision 持久化和 Chrome P00→P04 回放。当前仍缺配额治理、跨机器缓存、旧快照持续服务、真实 MySQL 部署恢复、餐厅节点与 Gate 7，不能宣称稳定生产可用或已完成 M1 MVP

## 已完成

| 工作流 | 状态 | 证据 |
|---|---|---|
| G3 求解器 Spike | 完成 | `spike/` 历史证据 |
| G4 求解器设计与约束分级 | 完成 | ADR-0003/0004 |
| G5 C1/C2/C4/C5/C6 与分层求解 | 阶段性完成 | 核心能力已通过 Gate 6；后续可根据应用集成、真实数据和用户验证继续修复或演进 |
| 日志与审计 | 完成 | 模块级、按级别每日文件、月度压缩归档 |
| Gate 6 Golden/降级/性能/接近度 | 通过 | `docs/test/reports/` |
| M1 求解器对外契约 | 已稳定并版本化 | ADR-0009/0011/0012/0013/0015；当前 `solver-p1-v2 / constraints-p1-v5 / parameters-p1-2026-08-26`，保留历史版本回放 |
| A1 功能模块设计 | 完成（V3.0） | 14 个跨里程碑一级功能域；M1 详细功能树保持稳定，M2–M4 补齐可追踪功能骨架，见 `docs/product/功能模块设计.md` |
| 产品功能完整性复审 | 完成（V1.0） | 产品全景→功能树追踪、遗漏项、用户新增细化和历史规格冲突，见 `docs/product/产品功能完整性审查.md` |
| A2 信息架构与 UI 设计 | M1 详细设计完成；全路线同步完成（V1.1） | 保留 M1 页面和关键低保真；补充规划/行中/回顾三模式、M2–M4 页面族、入口与组件边界，见 `docs/product/信息架构与UI设计.md` |
| A3 交互流程与状态机 | M1 详细设计完成；全路线同步完成（V1.1） | IF-01–IF-12 可进入实现；登记 IF-13–IF-24，并明确执行、Visit、小记、媒体、授权和回顾状态，见 `docs/product/交互流程与状态机设计.md` |
| A4 应用代码架构设计 | 完成（V1.0） | 模块化单体、分层依赖、应用用例、求解器网关、事务幂等、前端目录、测试架构与纵向切片，见 `docs/product/应用代码架构设计.md` |

最新稳定技术基线：全量 264 项测试通过；Golden 8/8；降级 8/8；杭州公开攻略综合接近度 0.975；数据校验 7/7；性能 PERF-12-3 P95 14.94ms、PERF-20-7 P95 19.32ms，均通过。当前机器契约为 `solver-p1-v2 / constraints-p1-v5 / parameters-p1-2026-08-26`，结果结构为 `trip-result-v2`。和风实现文件 Ruff 与隔离 strict mypy 通过；本轮前端 TypeScript 与 H5 production build 通过，production `dist/index.html` 已生成；正式 bundle 严格加载、生产组合根/FastAPI 三日七景点回放和 Chrome P00→P04 均通过，Chrome 控制台 0 warn/error，刷新后三日 Revision 节点顺序稳定。入口约 304 KiB 的既有性能警告仍保留为 P1 优化项。全仓 Ruff 仍有 46 个历史问题；全项目 strict mypy 最近完整基线仍为 154 条/27 个历史文件，尚未建立为绿色 Gate。该证据只证明技术可行性，不证明 H3 已被专家或用户证实。

状态口径：求解器**核心实现已阶段性完成**，不是永久冻结；M1 对外契约、约束语义和默认参数均已稳定并版本化。允许继续进行缺陷修复、内部重构、性能优化和基于真实验证的后续演进，但契约行为变化必须按 ADR-0009/ADR-0011 评审并升级相应版本。

## 正在进行

### A4：应用代码架构设计

- 状态：已完成
- 核心产物：`docs/product/应用代码架构设计.md`
- 关键结论：模块化单体；首切片 inline executor；通过 GenerationExecutor 可替换 Celery；Trip/Revision/Intent/SolverRun 分离；SolverGateway 隔离已稳定并版本化的求解器契约；M2–M4 只保留边界、不创建空模块
- 完成度：100%

### A5：API 与持久化数据模型同步

- 状态：已完成
- 核心产物：`docs/specs/api-contract.md` V2.0、`docs/specs/data-model.md` V2.0
- 关键结论：草稿/Intent/Trip/Revision 资源分离；无 `/regenerate`；到离交通事实分离；输入/结果 snapshot 版本化；草稿乐观锁、intent 原子领取、Revision/SolverRun 原子完成事务明确
- 完成度：100%

### A6：首个浏览器可操作纵向切片

- 状态：进行中
- 当前输入：A4 架构、A5 HTTP v1 契约与数据库模型、已稳定并版本化的求解器契约
- 首个实现切片：匿名会话 → 草稿 → 杭州景点 → GenerationIntent → inline SolverGateway → TripRevision → 恢复结果
- 已完成：A6-1 至 A6-5 应用、求解与数据库核心；A6-6 匿名身份、FastAPI HTTP v1、景点目录和 inline 组合根
- 浏览器进展：首轮 375px 门禁和本轮正式数据桌面 Chrome 回放均走通 P00→P04；正式回放使用 2026-08-27 至 2026-08-29 的真实和风天气、审核坐标和 42/42 高德 OD，验证返回上一步、按钮真实禁用/启用、7 景点选择、午晚餐、交通方式/距离/耗时、三日切换、13:30–16:00 湖滨、19:30 固定表演、刷新恢复和“＋规划新行程”；3/2/2 景点全部守恒且 0 个未排入
- 响应式与安全：375×812 完整页面通过；1280×800 下内容居中、无横向溢出、日期 Tab 三列等宽；健康路径控制台 0 error/warn；受控后端故障只展示稳定用户提示，不泄露 Token、request ID 或技术堆栈
- 下一步：完成和风/高德配额看板、限流/熔断、跨机器缓存与旧快照继续服务策略；再进入 A6-8.2 真实 MySQL 与部署恢复
- 完成度：约 98%（仅指首个纵向切片及其本地浏览器、行程质量、高德 Provider、JSON 发布适配器和生产启动门禁技术验证，不代表 M1 MVP）

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
- 本机未发现 MySQL/MariaDB 服务或 Docker，因此真实 InnoDB 双连接并发、服务器 TLS、备份和故障恢复仍未验证，不标记为生产 MySQL 已完成。

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

| 顺序 | 阶段 | 内容 | 当前状态 |
|---|---|---|---|
| 1 | A1 | 功能模块设计 | 已完成 |
| 2 | A2 | 信息架构、页面清单与 UI 设计 | 已完成 |
| 3 | A3 | 核心交互流程、页面状态与异常流程 | 已完成 |
| 3.5 | 产品功能完整性复审 | 全景需求追踪、缺口补齐与冲突登记 | 已完成 |
| 3.6 | A2.1/A3.1 | 全路线 UI/交互边界同步 | 已完成 |
| 4 | A4 | 应用代码架构、模块边界与依赖规则 | 已完成 |
| 5 | A5 | API 与持久化数据模型同步 | 已完成 |
| 6 | A6 | 首个浏览器可操作纵向切片 | 进行中（约 98%；真实 OD、真实天气、正式快照和生产 Chrome 回放已通过，下一步配额/快照持续服务治理、MySQL 与部署恢复） |
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

- FastAPI HTTP v1、匿名会话和组合根已完成首切片；尚未进行真实 MySQL 部署、外网服务启动和安全加固；
- Planning SQLAlchemy 仓储与迁移已完成；正式不可变 JSON PublishedDataProvider 已接入生产组合根并完成回放，但正式发布数据尚未迁入数据库发布表；
- 高德真实路网和和风真实三日天气均已完成严格快照、正式 bundle、Gateway 消费和生产回放；尚未完成配额看板/限流/熔断、跨机器缓存、旧快照持续服务和三日之外的正式气候基线；登录等其他真实外部 Provider 尚未接入；
- 午晚餐当前仍是软留白；具体餐厅节点、餐厅加入后的真实 OD 完整重排和新 Revision 流程尚未实现；
- Taro/React P00–P04、依赖锁定、TypeScript、H5 production build 和 Chrome 移动端/桌面端首轮交互门禁已完成；尚未完成多浏览器、弱网、长时会话和生产部署验证；
- A6 已有领域/应用、求解器、配置数据库、HTTP API、前端页面、真实高德/和风、正式 JSON 发布数据和本地生产 Chrome 闭环；由于真实 MySQL 部署、配额与快照持续服务治理、外网安全加固和部署恢复仍未完成，仍不能宣称普通用户可稳定生产使用；
- 全项目严格 Mypy 基线尚未清零；当前本轮新增文件在隔离导入检查下通过，但旧求解器、HTTP/数据库适配器与 Windows/POSIX 分支仍有 83 个既存类型错误，需另立技术债切片处理；
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

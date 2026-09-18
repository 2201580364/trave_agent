# CURRENT — 当前状态滚动快照

> 唯一的「现在」入口；历史在 [status-archive/](status-archive/)，稳定路线见 [project-roadmap.md](project-roadmap.md)。

- 更新时间：2026-09-18（M1 专家评分、有界优化和真实 OD 冷缓存本地实现完成，最终门禁与整批部署进行中）。
- 当前节点：`M1 后段 / Gate 7 / OM1`。M1 工程功能和本轮行程质量改造已完成本地页面验证；正式 Gate 7 仍缺整批服务器复验、域名/HTTPS、真实导游盲评和 8–10 名目标用户研究。
- 用户安排：先完成本地集中修复、自测与内置 Chrome 验证，稳定后统一构建镜像、推送仓库并在服务器复验；真实用户反馈后置。
- 最近提交基线：HEAD `7654e1f`（M1 工程收尾已由用户提交）；当前评分与有界优化工作区变更尚未提交，Git 提交/推送/分支操作由用户执行。
- 交付证据：[专家评分与真实 OD 验证](../test/reports/m1-expert-itinerary-review-20260918.md)、[M1 工程收尾验证](../test/reports/m1-engineering-close-20260918.md)；改造阶段状态见 [transformation-plan.md](transformation-plan.md)。

## 本轮验证基线

- Python3.12、uv0.8.15、uv.lock 开发依赖环境 `var/env/m1-close`，PYTHONUTF8=1。最终pytest全量632项通过，含专家评分、有界优化、反馈校准口、高德有限并发、旧worker接管竞态及conditional来源发布门禁。
- frontend：25项通过，类型检查通过；admin-web：51项通过，类型检查通过。
- Golden 8/8、接近度0.975；ruff、mypy252文件、分层159文件通过；OpenAPI实现83/契约86、code-only=0，3个计划/兼容端点仍只在契约中。
- 管理端61个操作的JSON成功响应具备结构化schema；OpenAPI生成TypeScript已同步。泛型用户端响应全量迁移不是S8-3范围。
- 内置Chrome实际执行：十景点三日生成、逐日查看、刷新恢复、历史、分享预览、访客只读；首次生成和替换中刷新（第2版），每任务一条求解记录。
- 管理端实际执行：登录、刷新经/me恢复、安全退出；修复Vite /admin 首页刷新重定向和退出后迟到401通知。
- 研究目录只复核初步覆盖：72条candidate、9分类、11区域、18夜间/固定时间、28室内/雨天、24非点几何、15关系线索，覆盖检查通过。不新增批量human_verified。

## 本地与服务器运行边界

- 本地API8000、H5 10086、管理端5173使用服务器MySQL23306/Redis26379；真实Gaode OD。未用研究数据库副本验收。
- 共享队列会被服务器旧worker消费。此次回归在队列空闲后临时暂停服务器worker，确保本地新worker执行；结束后已恢复服务器worker并停止本地测试worker。后续本地求解验收必须先协调worker，不把旧worker结果冒充新代码证据。
- 本轮页面回归结束后本地API/worker已停止；服务器worker已确认`Running=true / Paused=false`，避免共享队列继续被本地进程消费。
- 已部署镜像版本不代表本轮工作区：本轮没有部署。服务器使用外置挂载.env、日志、MySQL/Redis数据及published资源；旧源码目录此前已按用户确认清除。

## 已完成的现有工程收尾

- S8剩余管理响应契约、生成类型、结构化schema门禁；可复用内置浏览器E2E在 `frontend/e2e/m1-core-flow.mjs`，不是无头CI已上线声明。
- 后台异步执行、队列接管与旧执行者写回保护；首次/替换提交前持久化同一intent和请求，刷新后恢复，等待超时不误报任务终止。
- 详情与分享时长/时间/短距离如实展示；测试天气明确非真实预报；旧游客401提示与明确重新登录，不自动转移旧行程。
- 管理会话按用户裁决保留sessionStorage；[ADR-0029](../decisions/ADR-0029-admin-tab-session-recovery.md)替代ADR-0020相关条款；刷新必须经服务端/me，不保存密码，旧请求不恢复已退出主体。
- OD阶段耗时、缓存命中、远程请求/失败与等待计数持久化；本轮按Accepted ADR-0028启用固定版本评分与有界目标，无新增迁移或第三方依赖。
- 断桥/灵隐已按授权通过新修订→证据比对核验→审核→投影→发布；未直接修改published。版本及审计证据见报告。

## 专家评分与真实 OD 结果

- 运行版本为 `solver-p1-v2 / trip-result-v2 / constraints-p1-v9 / parameters-p1-2026-09-18a`；评分策略 `expert-itinerary-review-v1`，默认权重 `expert-default-2026-09-18`。
- 七维固定评分为 G地理20、V游览价值20、P节奏15、R衔接15、M餐休12、F体力8、U明确意愿10；有界优化最多6轮、每轮40候选、256日期路由、15秒搜索墙钟，严格改善且指纹去重。
- 内置Chrome真实冷缓存十景点三日：3天均非空、10/10排入、硬违规0、评分88.4、严重项0、证据1000/1000；断桥/平湖/博物馆同日，飞来峰/灵隐同日，灯光秀与游船分日。
- 冷缓存全新数据版本0命中/174远程请求/0失败，OD54.612秒、端到端58.169秒；原基线270请求/361.064秒。暖缓存174命中/0请求/0失败，端到端5.185秒。
- 0.2秒共享间隔首次并发实测触发3次限流并安全失败；默认改为0.3秒、8路有限并发后第二次全新版本通过。`M1-OD-LATENCY-001`及`SOLVER-QUALITY-005/006/007`更新为`resolved_local`，待整批部署复验。
- 剩余FATIGUE、宽邻域折返和首日晚餐60分钟均为warning；不为跨过90分提前停止线而放宽规则。反馈在线调权不属于M1，仅保留至少200条反馈/80名用户、单维±3个百分点且需人工批准的离线候选校准口。

## 待人工补证与后置验收

- `DEPLOY-DATA-001`已完成：断桥40/70/90分钟、灵隐建议150分钟、音乐喷泉建议60分钟均保持published；博物馆第5版 `place_revision_fc3857f893f84f0aa016db2149432ac8` 已发布为室内、60–180分钟、建议120分钟，旧第4版退役。内置Chrome管理端14/14核验、0待办；用户端室内/120分钟可见。历史行程不原地重算。
- `ADMIN-SOURCE-GATE-001`本地解决：发布上下文纳入闭馆日、日期例外及其来源；active证据引用conditional来源稳定返回`CONDITIONAL_SOURCE_STAGING_ONLY`，未核验闭馆/例外返回`TIME_RULE_UNRESOLVED`。旧博物馆第4版实库检查已阻断，新第5版仅approved来源且可发布；代码尚未随稳定批次部署。
- 钱江新城灯光秀048时间证据差异继续保留，不自动修改或豁免。天气fixture虽已如实标注，不代表新日期真实天气覆盖已验收。
- 本轮后端全量pytest、mypy252文件、ruff、文档、159文件分层、frontend25项、admin-web51项、两端类型检查、Golden8/8、接近度0.975和契约生成均通过。
- 正式clean image build与服务器整批复验仍待完成。本机Docker Desktop因Windows/WSL遗留AF_UNIX reparse handle无法启动，需重启Windows释放后继续；未清除镜像、volume、登录或项目数据。无域名，HTTPS与环境锁定继续后置。
- “堪比20年导游经验”是待证产品目标；需至少3名独立杭州带团导游（其中至少1名约20年经验）对不少于30组输入做隐藏算法名称的配对盲评，工程自测不能声明资历等价。
- 8–10名目标用户可追溯访谈、去标识研究结论、G7体验与assumptions回写后置；H1–H12不以内部测试冒充验证。
- M1最终Gate7尚未通过，不启动M2，不将当前工程收尾等同于适合正式外部招募。

## 下一步

1. 重启Windows释放Docker Desktop遗留socket；确认本地Linux builder恢复，不执行factory reset。
2. 本地构建唯一release tag并smoke，推送CCR；服务器备份、Compose更新并复验ADMIN-SOURCE-GATE-001、异步生成、真实OD、评分审计及管理流程。
3. 用户人工检验通过后开展真实导游盲评和8–10名目标用户研究；反馈达到治理门槛后再讨论离线校准与版本发布。

## In-flight 区

| 任务 | 分支 | 触碰文件 | 状态 |
|---|---|---|---|
| 专家评分、有界优化与冷 OD 性能（H2/H3/H7） | dev | solver评审/质量/分段、gateway/gaode/composition、对应测试、ADR/规格/运维/报告/账本 | 实现、真实页面与全量门禁完成；Docker需Windows重启后继续本地构建和整批部署复验 |

## 关键事实速查

- 断桥新published修订 `place_revision_2800a9b1a7364394866c388c596b5265`；灵隐 `place_revision_f0f99afcb9c941d78bf36e8840af869b`。投影版本 `hangzhou-reviewed-facts-20260918-v1`；历史保留。
- 现有求解契约 `solver-p1-v2 / trip-result-v2 / constraints-p1-v9 / parameters-p1-2026-09-18a`。
- 数据库head `0016_expand_alembic_version`；本轮无迁移。本机不安装/启动MySQL/Redis，凭证不入仓库和报告。
- Gate7 protocol SHA-256 `b791f0558dfc93af4cc919ec6dd9b09d1251f8f1d54b7bc0bb8809eade742d89`。

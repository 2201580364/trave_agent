# CURRENT — 当前状态滚动快照

> 唯一的「现在」入口。每轮任务结束时更新本文件；历史细节看 [status-archive/](status-archive/)，跨里程碑稳定路线看 [project-roadmap.md](project-roadmap.md)。

- 更新时间：2026-09-17（管理端证据审核时间序列化修复、API 镜像发布与浏览器验收）
- 当前节点：`M1 后段 / Gate 7 / OM1；发布目录动态数据库接入已部署；用户端按请求读取最新 published Projection；关系裁决形成的互斥组进入选点与求解约束；OD近邻分天保护与十景点整段质量修复已提交；12 条代表性候选已完成审核、批次发布与用户可见性回归；历史问题清单已收口，真实OD部署体验待验收`
- 线上验收：API/用户端/管理端已更新为 `ccr` 仓库的固定 digest；管理端为 `admin-20260917-httpuuid1`（`5d05...236d6`），API 为 `api-20260917-reviewedat1`（`98e490...aa574`）。配置改为精确只读挂载 `/etc/travel-agent/api/.env`，日志、MySQL/Redis 数据与 published 数据均为宿主机挂载。数据库 migration `0016_expand_alembic_version`、readiness、备份校验、用户端行程恢复、服务器裸 HTTP 管理端真实“新建修订”，以及候选列表 422 修复后的浏览器加载均通过；真实 OD 仍保持 approximate，待单独验收。
- 本轮自动验证基线（Python3.12锁定环境、PYTHONUTF8=1）：后端全量606项通过；Golden8/8；ruff（src/tests/scripts）、全仓mypy242文件、153文件分层通过。无新增迁移。
- 本轮浏览器验证：内置Chrome完成平湖秋月单景点选择→确认→生成→刷新，显示1已安排/0未排入、无景点间接驳；原13景点历史行程也能刷新恢复。此轮不冒充真实OD端到端验收。
- 已有关系约束基线：已发布且 `human_verified` 的 `selection_exclusion_groups` 随数据库目录加载到 `PublishedAttraction`；选点接口与 `ProductionSolverGateway` 双层拒绝同组重复选择，已有数据库/求解器回归随本轮全量通过。
- 最近提交基线：HEAD `980462f`（OD 出入园端点已由用户提交）；本轮缓存归位、镜像流程、真实OD接线、回放与单景点改动待用户手动提交。

## 最近三轮已完成

- 2026-09-16 问题清单收口（H3，已提交90c94fd）：TYPE-001/OD-QUALITY-001/ADMIN-DATA-001/DATA-PLACE-002关闭；新增修复O17权限500、投影data_verified持久化、关系来源父子端点门禁不一致。平湖秋月v4通过应用接口发布，data_verified=true且复用solver_node_id=25。详见 [收口报告](../test/reports/issue-ledger-close-20260916.md)。
- 2026-09-16 十景点质量（H3，ADR-0027，已提交99e5ac4；近邻吸附补丁已随90c94fd提交）：恢复跨日可行性后重平衡实际负载；固定场次日执行完整用餐/普通建议时长/下午展开；真实航次保留星期和有效日期，撤销错误合窗。详见 [质量报告](../test/reports/solver-quality-20260916.md)。
- 2026-09-16 七景点近邻（已提交731da1b）：OD强近邻在分天再平衡时保留；7点浏览器生成和两组近邻同日验证完成，历史细节见本月归档。

## 下一步（按顺序）

1. 对 72 条杭州研究目录做初步扩张和覆盖复核；暂不以批量扩张至 50–75 条 `human_verified` 作为当前退出条件。
2. 收尾 R0.2-06 按需真实有向 OD 子图：现有版本化适配器、文件/Redis 缓存、不可变子图 hash 和回放已通过定向回归；出园→入园端点已实现；服务器高德步行鉴权已通过，仍需冷缓存生成/恢复、Redis缓存/配额和部署级验收。
3. 完成 S8 剩余响应契约与 E2E 覆盖核对；R0.3 已按本地构建、镜像仓库、服务器拉取的流程部署到内部18080，后续仅按变更继续这一发布流程。HTTPS等待域名，真实用户访谈和研究结论按用户安排后置。

## 本地运行验证（2026-09-17）

- API8000、管理端5173、H5 10086已恢复本轮代码，本地明确使用approximate模式；启动日志在 `var/reports/m1-close-20260917/`。服务器已部署本轮m1a镜像；真实OD未启用，仍为approximate。

## 活跃风险

- `DEPLOY-DATA-001`：服务器published仍含断桥/音乐喷泉1分钟、博物馆mixed、灵隐寺120分钟等与本地审核结果差异；代码部署不迁移业务数据，须按正常修订审核发布闭环处理，禁止直接覆盖数据库。

- `M1-OD-LATENCY-001`：真实OD仍为同步生成；10点×3模式冷缓存最多270次请求，节流可能耗时数分钟。响应超时/恢复体验尚未收尾，必须在真实OD试用前处理验证。
- Docker Desktop本机Linux/amd64构建已通过；使用服务器缓存的官方基础镜像解决Docker Hub连接超时。用户确认新仓库ccr，三镜像已推送/服务器拉取并部署。
- 高德Web服务凭证1次步行路径探针通过（10000）；不代表公交/驾车、Redis共享缓存或完整生成验收通过。
- `SOLVER-SINGLE-001` 已修复：单景点生成无需跨点OD；28项专项与Chrome生成/刷新通过。
- 问题清单 `var/reports/admin-issue-ledger-20260915.json` 已追加单景点修复及真实OD冷缓存待处理项；版本化证据见本月归档。不能沿用历史“问题全部收口”作为本轮结论。

- `SOLVER-QUALITY-005` 新观察：平湖秋月与断桥残雪已同日，但同日内方向仍由近似OD决定，当前可能为断桥→平湖；未违反 C1/C2/C4/C5/C6，待真实有向OD或显式西湖游线规则支持后优化。
- 本地近似OD仍不是实时路网；本轮只修正“未知近似短边误展示为步行”的标签与缓冲，不替代R0.2-06真实有向OD子图。
- 2026-09-10 提交核对仍需裁决：S6 sessionStorage + /me 会话恢复与 ADR-0020 持久化禁令存在边界差异；几何修复的客户端文案与 error-messages.md 单一文案源存在边界差异。
- 2026-09-17 复核确认：12 条代表性候选已完成六项审核准备度、Projection、批次发布和用户端可见性回归；研究目录当前只做初步扩张，不启动大规模 `human_verified` 扩张。钱江新城灯光秀 048 的时间证据差异仍单独保留，不自动修改或豁免。

- Gate 1 真实用户研究补证按用户安排后置：当前先完成其余 M1 工程项和可供用户体验的受控环境；M1 最终决策前仍需补齐 8–10 名目标用户访谈、去标识结论和 assumptions 回写。
- 历史账本记载的测试计数互相矛盾（352/363/367/370/…/432），以本文件顶部稳定测试基线为准；旧计数属阶段性快照，不代表回退。
- 服务器真实 MySQL 已通过 readiness 核对至 `0016_expand_alembic_version`；后续迁移或部署仍需保留 readiness、备份与隔离恢复核对。
- H1–H12 全部「未验证」；自动化测试、Chrome 验收或团队内部判断均不能冒充 H3/H11 的真实用户证据。
- Windows 偶发 `WinError 10055` 套接字错误为环境 flaky（隔离复跑即过），非业务回归。

## In-flight 区（当前同会话工作）

历史任务登记已完整迁至 [本月归档](status-archive/2026-09.md)，不再把历史“进行中/待提交”记录当作活跃并行任务。

| 任务 | 分支 | 触碰文件 | 状态 |
|---|---|---|---|
| 容器配置与日志挂载（G7-R0.3） | dev | runtime_config及测试、API启动脚本、deploy/production、部署文档、CURRENT、本月归档 | 已实现待用户提交；`api-20260917-mounted-env1` 已部署，配置、日志、MySQL/Redis/published 数据均已挂载并回归；用户确认后已清理旧源码目录 |
| 天气快照缺日错误分类（H3/C5） | dev | infrastructure/solver/gateway、gateway测试、CURRENT、本月归档 | 进行中；缺天气是数据不可用，不应将合法用户输入标为终止失败 |
| 本地管理端代理修复 | dev | admin-web/vite.config.ts、CURRENT、本月归档 | 已修复并验证代理readiness、47项测试、类型检查通过 |
| 本地镜像构建与部署验收 | dev | deploy/production配置（如构建发现问题）、CURRENT、本月归档；var/reports/m1-close-20260917制品 | 三镜像本地构建/推送/部署完成；备份校验与readiness通过，数据差异阻断完整验收 |
| 工作区归位与镜像流程 | dev | README、pyproject、.dockerignore、项目部署技能、API Dockerfile、ops文档、CURRENT、本月归档 | 完成；API非root权限已在Linux镜像验证 |
| 单景点与 OD 回放完整性（H3/C6） | dev | solver/subgraph、gateway与C6/subgraph测试 | 已实现、自测和Chrome验证，待用户提交 |
| 真实 OD 接线（H3/C6） | dev | infrastructure/solver/{gateway,database_published}、http/composition、gateway测试、.env.example | 离线接线通过；服务器步行鉴权1次通过；冷缓存生成/共享缓存/部署验收未完成 |
| 本地共享服务器数据源与旧部署目录清理 | dev | `.env`（gitignored）、deploy/production、CURRENT、本月归档、问题清单 | 已完成：旧源码目录已按用户确认删除；MySQL/Redis 已改为 `0.0.0.0:23306/26379`，本地 `.env` 已直连服务器 IP 并实测读取线上记录、Redis PING 成功；容器健康与 API readiness 通过 |
| 管理端裸 HTTP 操作 ID 兼容修复 | dev | admin-web API/错误管线/各写入页面及测试、deploy/production、CURRENT、本月归档、问题清单 | 已完成；`crypto.randomUUID` 回退覆盖全部管理端写入入口，镜像已按 `5d05...236d6` 部署，Chrome 点击新建修订创建第4版 candidate，edge记录POST 201 |
| 管理端证据审核时间序列化修复 | dev | place_catalog仓储与审核HTTP测试、API镜像、CURRENT、本月归档、问题清单 | 已完成待用户提交；仓储统一 ISO 8601 序列化，线上唯一无时区几何审核时间已定点归一化，API `98e490...aa574` 已部署；Chrome 候选列表60条和异常修订均恢复加载 |

## 关键事实速查

- 研究库 `.local/research.db`：平湖秋月最新 published v4=`place_revision_5ccfec95107f4757a5d112f59410cdc1`，Projection=`solver_projection_f46fb0c9da824b2bae7de03c3a65e582`，`data_verified=true`、`solver_node_id=25`；浙江省博物馆孤山馆区 published v4 为室内。
- 求解器契约：`solver-p1-v2 / trip-result-v2 / constraints-p1-v8 / parameters-p1-2026-09-16b`；历史 Revision 不迁移、不覆盖、不原地重算。
- Gate 7 protocol 规范化 SHA-256：`b791f0558dfc93af4cc919ec6dd9b09d1251f8f1d54b7bc0bb8809eade742d89`。
- 正式发布 bundle：`var/published/hangzhou-published-2026-08-27-v1.json`（7 景点 human_verified 坐标 + 42/42 高德 OD + 真实和风三日天气）。
- 本机禁止部署/启动 MySQL/Redis；本地开发组合根用明确标注的近似 fixture，生产组合根只加载严格验证的 published 快照。

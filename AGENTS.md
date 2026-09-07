# trave_agent — Agent 工作正本（L0，每次会话必读）

## 一句话定位

旅行助手：输入目的地，自动规划旅行路线，搞定衣食住行。核心命题是「**AI 求解器排的行程比人排更合理**」。

## 当前状态入口

当前节点、测试基线、下一步与活跃风险**只看** [docs/process/CURRENT.md](docs/process/CURRENT.md)（滚动快照，每轮更新）。跨里程碑稳定路线见 [docs/process/project-roadmap.md](docs/process/project-roadmap.md)；历史轮次记录在 [docs/process/status-archive/](docs/process/status-archive/)，只按需查阅、不全文读。

## 技术栈速览（对齐实现，无虚报）

| 层 | 选型 |
|---|---|
| 用户前端 | Taro 4 + React 18 + TypeScript（H5 + 微信小程序目标），Zustand |
| 管理端 | 独立 `admin-web/`：React 19 + TypeScript + Vite + React Router + Ant Design + Vitest（ADR-0020） |
| 后端 | Python 3.12（`requires-python >=3.12`，CI 锁 3.12；本地开发可为更高小版本）+ FastAPI + SQLAlchemy 2.0 + Alembic；异步任务为自研 `travel-agent-holiday-worker`（无 Celery）；依赖版本由 `uv.lock` 锁定（ADR-0024） |
| 核心求解器 | OR-Tools（M1 分层：已发布 OD 的确定性聚类与日负载均衡 → TSP-TW 天内排序 → 约束校验 → 时间填充） |
| 存储 | MySQL 8（服务器）+ SQLite（本地开发/研究库）+ Redis（Provider 治理，服务器侧） |
| 外部 API | 高德地图（路网/OD）、和风天气（X-QW-Api-Key 请求头认证）、微信开放平台（规划中）；LLM 仅用于 O17 节假日抽取（供应商中立 OpenAI-compatible 适配器） |

## 四条核心原则（不可违背）

1. **大模型做「软」的事，引擎做「硬」的事**：LLM 负责理解/表达/摘要/解释；求解、校验、约束、路由由确定性引擎负责。硬事实只从结构化数据读取，**LLM 不得生成**，管理员也不能绕过发布门禁。
2. **硬约束 100% 通过**：C1 闭馆日、C2 入园时间窗、C4 时间锚点、C5 极端天气、C6 交通衔接违反数必须为 0；体力是软约束，不得硬拦。
3. **数据质量门禁**：Place 字段绑定 source registry/field dictionary、Revision、审核状态和发布投影；conditional 只能 staging。
4. **假设可追溯**：任何代码/测试/文档都回溯到 [docs/assumptions.md](docs/assumptions.md) 的 `H-x` 编号或需求编号。

## 任务类型 → 阅读路由表

| 任务类型 | 先读 |
|---|---|
| 任何任务（第一步） | 本文件 → [docs/process/CURRENT.md](docs/process/CURRENT.md) → **[.claude/rules/file-management.md](.claude/rules/file-management.md)（文件写入位置纪律）+ [.claude/rules/git-safety.md](.claude/rules/git-safety.md)（Git/删除硬规则）** |
| 求解器/约束改动 | [docs/domain/](docs/domain/) + [.claude/rules/solver.md](.claude/rules/solver.md) + ADR-0003/0004/0009~0015 |
| Git 操作/文件删除（任何任务都适用） | [.claude/rules/git-safety.md](.claude/rules/git-safety.md)（硬规则，用户要求） |
| 写规则/写文档/新建文件（任何任务都适用） | [.claude/rules/file-management.md](.claude/rules/file-management.md)（写入位置对照表，用户要求） |
| 并行开发/多会话协作 | [.claude/rules/parallel-workflow.md](.claude/rules/parallel-workflow.md)（一会话=一分支=一能力域 + In-flight 登记纪律） |
| 地点数据/审核/发布 | [docs/product/管理端功能模块设计.md](docs/product/管理端功能模块设计.md) + ADR-0018/0019 + [docs/domain/地点数据来源与采集规范.md](docs/domain/地点数据来源与采集规范.md) |
| O17 节假日同步 | ADR-0021 + [docs/product/O17中国法定节假日历自动同步设计.md](docs/product/O17中国法定节假日历自动同步设计.md) |
| O18 数据采集 | ADR-0022 + [docs/product/O18地点数据采集与关系识别设计.md](docs/product/O18地点数据采集与关系识别设计.md) |
| API 契约/数据模型 | [docs/specs/api-contract.md](docs/specs/api-contract.md) + [docs/specs/data-model.md](docs/specs/data-model.md) |
| 测试/验证 | [docs/test/](docs/test/)（gate7-validation-plan 等） |
| 部署/运维 | [docs/ops/](docs/ops/) + [deploy/production/](deploy/production/) |
| 历史轮次细节 | [docs/process/status-archive/](docs/process/status-archive/) 按月切片 |
| 文档地图/阅读顺序 | [docs/00-index.md](docs/00-index.md) |

## 工作流（假设驱动的 AI 协作开发）

```
G0 假设登记 → G1 用户研究 → G2 需求规格化 → G3 技术 Spike（风险前置）
→ G4 详细设计 + ADR → G5 约束 TDD 实现 ⇄ G6 分层测试 → G7 假设复盘
```

每个阶段有退出准则（Gate），不满足不进下一阶段。最不确定的（求解器、数据质量、用户需求）**最先验证**，不按自然实现顺序排。Gate 定义、权威来源优先级与冲突处理见 [docs/process/gates.md](docs/process/gates.md)；资料冲突时停止实现并报告，不得自行选用旧版本。

## M1 最终约束基线（ADR-0004）

| 类型 | 编号 | 约束 |
|---|---|---|
| 硬 | C1 | `weekday ∈ close_days` 时不可排，支持节假日例外 |
| 硬 | C2 | `arrival ∈ [open, min(last_entry, close − 0.6×duration)]` |
| 硬 | C4 | 首日到达、末日离开与返程时间锚点 |
| 硬 | C5 | 极端天气排除室外景点 |
| 硬 | C6 | 基于 OD 耗时的真实交通衔接 |
| 软 | S1 | 实际游览不足建议时长时提示，默认最低比例 60% |
| 软 | S2 | 高体力景点分天均衡 + 节奏提示，不设置 3/5/8 星硬上限 |

天内目标函数为 `min Σ travel`；默认分天先保护 OD 近邻，再平衡每日数量与建议时长负载；体力均衡只是分天启发式。任何改变目标函数或恢复体力硬上限的提议必须新写 ADR。

## 关键约定

- 求解器改动必须附带对应约束单测（详见 [.claude/rules/](.claude/rules/)）；算法/数据改动必须跑 Golden Case 回归。
- 新增第三方依赖需写 ADR；每个 PR 关联 `H-x` 编号。
- 测试：pytest；lint/type：ruff + mypy。
- 管理端状态分开报告「已设计/已实现/已部署/已验收」；页面存在或数据库表存在都不等于 OM1 完成。
- 管理端不能直连 MySQL；published 只能通过共享 application/domain 发布用例。
- 真实凭证（API Key、密码、token）不入仓库、不入日志、不入文档；`.env` 被 Git 忽略。
- 本机禁止安装/启动 MySQL/Redis；服务器操作须在授权服务器上执行。
- **Git 提交/推送/合并等写操作一律由用户手动执行，AI 禁止自动进行；删除文件前必须列清单获用户确认**——完整分级与纪律见 [.claude/rules/git-safety.md](.claude/rules/git-safety.md)。
- **并行开发遵守「一会话=一分支=一能力域」：任务启动先在 CURRENT.md In-flight 区登记触碰文件清单，登记清单不得有交集；并行期 Alembic 迁移与 `.local/*.db` 互斥**——完整纪律见 [.claude/rules/parallel-workflow.md](.claude/rules/parallel-workflow.md)。
- **账本时效：任务实现完成即更新账本（不等合并）；开工前发现账本与 git log 不一致，顺手收口（单会话同样适用）**——见 [.claude/rules/parallel-workflow.md](.claude/rules/parallel-workflow.md) 第八节。
- 提交边界按「可验收能力域/里程碑切片」划分，不按单个 API/字段/按钮拆分（详见 status-archive 账本头）。

## 权威来源简表

发生冲突时按以下顺序判断：最新且已接受的 ADR → 当前 Accepted 规格 → 领域规范/数据模型 → 假设登记册 → `.claude` rules/skills/agents → 历史产品文档与 Spike。`.claude` 控制文件必须追随 ADR 和规格，不能覆盖它们。

## 团队背景（影响节奏）

- 团队无 OR/运筹背景 → 求解器任务时间盒放宽，优先 Spike 验证可行性。
- M1 可能单人开发 → 简化流程，倾向可丢弃 Spike 与自包含原型。
- 杭州先行：G7-R1 先达到约 50–75 个 `human_verified` Place；M1 受控上线目录原则上 80–120 个。AI 可辅助候选/抽取，但来源、冲突、访问点和硬事实必须人工审核。

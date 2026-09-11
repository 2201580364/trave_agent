# 文档地图与阅读顺序

> 新人 / 新会话的入口。按角色选择阅读路径。

## 文档分层（L0–L3）

| 层 | 内容 | 位置 |
|---|---|---|
| **L0 正本** | 项目定位、技术栈、核心原则、任务路由表、约束基线、关键约定 | [AGENTS.md](../AGENTS.md)（CLAUDE.md 为其薄指针） |
| **L1 滚动状态** | 当前节点、测试基线、最近完成、下一步、活跃风险、In-flight 登记区 | [process/CURRENT.md](process/CURRENT.md)（≤150 行，每轮更新） |
| **L2 稳定路线与规范** | 跨里程碑路线图、Gate 定义、产品/领域/规格/决策/测试/运维文档 | [process/project-roadmap.md](process/project-roadmap.md)、[product/](product/)、[domain/](domain/)、[specs/](specs/)、[decisions/](decisions/)、[test/](test/)、[ops/](ops/) |
| **L3 历史归档** | 逐轮续接记录切片，只按需查阅、永不全文读 | [process/status-archive/](process/status-archive/) |

**新会话阅读顺序**：先读 [AGENTS.md](../AGENTS.md) → 再读 [process/CURRENT.md](process/CURRENT.md) → 按任务类型查 AGENTS.md 的「任务类型 → 阅读路由表」进入 L2 对应文档。只有需要历史细节时才进 L3。

## 按角色

| 角色 | 阅读顺序 |
|---|---|
| 产品 / 投资人 | [process/CURRENT.md](process/CURRENT.md) → [process/project-roadmap.md](process/project-roadmap.md) → [product/产品功能完整性审查.md](product/产品功能完整性审查.md) → [product/功能模块设计.md](product/功能模块设计.md) → [product/管理端功能模块设计.md](product/管理端功能模块设计.md) → [product/信息架构与UI设计.md](product/信息架构与UI设计.md) → [product/交互流程与状态机设计.md](product/交互流程与状态机设计.md) → [product/应用代码架构设计.md](product/应用代码架构设计.md) → [assumptions.md](assumptions.md) → [product/旅行助手产品文档.md](product/旅行助手产品文档.md) |
| 工程师（后端/求解器） | [process/CURRENT.md](process/CURRENT.md) → [process/project-roadmap.md](process/project-roadmap.md) → [product/应用代码架构设计.md](product/应用代码架构设计.md) → [assumptions.md](assumptions.md) → [product/M1 MVP技术选型文档.md](product/M1 MVP技术选型文档.md) → [domain/](domain/) |
| 工程师（数据） | [process/CURRENT.md](process/CURRENT.md) → [process/project-roadmap.md](process/project-roadmap.md) → [decisions/ADR-0018-place-catalog-and-solver-projection.md](decisions/ADR-0018-place-catalog-and-solver-projection.md) → [product/O18地点数据采集与关系识别设计.md](product/O18地点数据采集与关系识别设计.md) → [decisions/ADR-0022-data-collection-staging-and-relation-clues.md](decisions/ADR-0022-data-collection-staging-and-relation-clues.md) → [domain/地点数据来源与采集规范.md](domain/地点数据来源与采集规范.md) → [test/gate7-data-deployment-readiness-plan.md](test/gate7-data-deployment-readiness-plan.md) → [specs/data-model.md](specs/data-model.md) → [domain/开放时间数据规范.md](domain/开放时间数据规范.md) → [research/README.md](research/README.md) |
| 数据运营 / 审核 | [process/CURRENT.md](process/CURRENT.md) → [product/管理端功能模块设计.md](product/管理端功能模块设计.md) → [product/人工核验操作路径.md](product/人工核验操作路径.md) → [product/O18地点数据采集与关系识别设计.md](product/O18地点数据采集与关系识别设计.md) → [product/O17中国法定节假日历自动同步设计.md](product/O17中国法定节假日历自动同步设计.md) → [decisions/ADR-0019-admin-console-and-governance-boundary.md](decisions/ADR-0019-admin-console-and-governance-boundary.md) → [decisions/ADR-0021-ai-synchronized-cn-holiday-calendar.md](decisions/ADR-0021-ai-synchronized-cn-holiday-calendar.md) → [decisions/ADR-0022-data-collection-staging-and-relation-clues.md](decisions/ADR-0022-data-collection-staging-and-relation-clues.md) → [domain/地点数据来源与采集规范.md](domain/地点数据来源与采集规范.md) → [test/gate7-data-deployment-readiness-plan.md](test/gate7-data-deployment-readiness-plan.md) → [specs/data-model.md](specs/data-model.md) |
| 测试 / 验证 | [assumptions.md](assumptions.md) → [process/gates.md](process/gates.md) → [specs/](specs/) → [test/README.md](test/README.md) → [test/gate7-validation-plan.md](test/gate7-validation-plan.md) → [test/gate7-data-deployment-readiness-plan.md](test/gate7-data-deployment-readiness-plan.md) → [ops/gate7-controlled-h5-docker-deployment.md](ops/gate7-controlled-h5-docker-deployment.md) → [test/gate7-research-environment.md](test/gate7-research-environment.md) |

## 目录结构

```
docs/
  00-index.md            ← 你在这里（文档地图 + 分层说明）
  assumptions.md         ★ 假设登记册（H1-H12，工作流账本）
  product/               产品全景、用户/管理功能架构、完整性审查、UI/交互和技术选型文档
  domain/                ★ 旅行领域规范（硬事实唯一来源，求解器与 LLM 都从这里读）
  decisions/             ADR 架构决策记录
  specs/                 需求规格 + Given/When/Then 验收标准
  research/              用户研究计划 + 结论
  test/                  测试方案 + Golden Cases + 验证报告
  ops/                   部署、外部 Provider、迁移与恢复操作说明
  process/               AI 协作开发 Gate、完整路线图、CURRENT 滚动状态与状态归档
    CURRENT.md           ★ 当前状态滚动快照（新会话必读 L1）
    project-roadmap.md   跨里程碑稳定路线（L2）
    project-status.md    归档账本头 + 术语 + 明确未完成（只追加）
    status-archive/      按月历史切片（L3，按需查阅）
data/
  governance/            ★ 可提交、非敏感、版本化的来源登记与采集字段字典
```

## 命名约定

- `M1–M4`：产品路线里程碑；
- `OM1–OM4`：管理侧能力里程碑，分别支撑对应用户产品阶段的数据、审核、发布和治理；
- `P0–P2`：实现优先级；
- `ADM-*`：管理侧原子功能编号；`O00–O17`：管理端页面编号；
- `G0–G7`：假设驱动开发 Gate；
- 历史兼容机器 ID 中的 `p1/P1`（如 `solver-p1-v1`）不再作为产品阶段术语；当前版本以对应 ADR 和机器契约报告为准。

## 核心概念

- **假设（H-x）**：产品待验证的命题，是工作流的最小单位。任何工作都回溯到某个 H-x。
- **硬事实**：开放时间、闭馆日、价格等不可由 LLM 生成、只从结构化数据读取的信息。
- **硬约束**：必须满足、否则行程不成立的条件（闭馆日、入园时间窗、时间锚点、极端天气和真实路网衔接）；体力属于软约束。
- **Gate**：阶段退出准则，不满足不进下一阶段。

## 维护约定

- 当前节点/测试基线/下一步变更 → 更新 [process/CURRENT.md](process/CURRENT.md)（唯一状态入口，不在其他文件复述节点）
- 假设状态变更 → 更新 [assumptions.md](assumptions.md)
- 技术决策 → 新增 [decisions/](decisions/) 下的 ADR
- 领域规范变更 → 更新 [domain/](domain/) 并通知数据与求解器两方
- 管理身份、审核、发布或治理边界变更 → 更新 [product/管理端功能模块设计.md](product/管理端功能模块设计.md) 和对应 ADR/API/数据模型
- AGENTS.md 正本变更后 → 运行 `python scripts/sync_agents_docs.py` 同步 CLAUDE.md 等派生入口

- [ADR-0025：show 多场次求解与候选时间规则删除](decisions/ADR-0025-show-sessions-and-candidate-time-rule-deletion.md)：H3/C2，多场次选择、候选删除与审核停用边界。

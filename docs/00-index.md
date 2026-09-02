# 文档地图与阅读顺序

> 新人 / 新会话的入口。按角色选择阅读路径。

## 当前状态入口

任何新会话先读 [process/project-status.md](process/project-status.md)，再读 [process/project-roadmap.md](process/project-roadmap.md)。前者记录每轮当前状态和续接点，后者记录用户侧 M1–M4、管理侧 OM1–OM4 的稳定顺序、依赖和退出条件。

## 按角色

| 角色 | 阅读顺序 |
|---|---|
| 产品 / 投资人 | [process/project-status.md](process/project-status.md) → [process/project-roadmap.md](process/project-roadmap.md) → [product/产品功能完整性审查.md](product/产品功能完整性审查.md) → [product/功能模块设计.md](product/功能模块设计.md) → [product/管理端功能模块设计.md](product/管理端功能模块设计.md) → [product/信息架构与UI设计.md](product/信息架构与UI设计.md) → [product/交互流程与状态机设计.md](product/交互流程与状态机设计.md) → [product/应用代码架构设计.md](product/应用代码架构设计.md) → [assumptions.md](assumptions.md) → [product/旅行助手产品文档.md](product/旅行助手产品文档.md) |
| 工程师（后端/求解器） | [process/project-status.md](process/project-status.md) → [process/project-roadmap.md](process/project-roadmap.md) → [product/应用代码架构设计.md](product/应用代码架构设计.md) → [assumptions.md](assumptions.md) → [product/M1 MVP技术选型文档.md](product/M1 MVP技术选型文档.md) → [domain/](domain/) |
| 工程师（数据） | [process/project-status.md](process/project-status.md) → [process/project-roadmap.md](process/project-roadmap.md) → [decisions/ADR-0018-place-catalog-and-solver-projection.md](decisions/ADR-0018-place-catalog-and-solver-projection.md) → [product/O18地点数据采集与关系识别设计.md](product/O18地点数据采集与关系识别设计.md) → [decisions/ADR-0022-data-collection-staging-and-relation-clues.md](decisions/ADR-0022-data-collection-staging-and-relation-clues.md) → [domain/地点数据来源与采集规范.md](domain/地点数据来源与采集规范.md) → [test/gate7-data-deployment-readiness-plan.md](test/gate7-data-deployment-readiness-plan.md) → [specs/data-model.md](specs/data-model.md) → [domain/开放时间数据规范.md](domain/开放时间数据规范.md) → [research/README.md](research/README.md) |
| 数据运营 / 审核 | [process/project-status.md](process/project-status.md) → [product/管理端功能模块设计.md](product/管理端功能模块设计.md) → [product/人工核验操作路径.md](product/人工核验操作路径.md) → [product/O18地点数据采集与关系识别设计.md](product/O18地点数据采集与关系识别设计.md) → [product/O17中国法定节假日历自动同步设计.md](product/O17中国法定节假日历自动同步设计.md) → [decisions/ADR-0019-admin-console-and-governance-boundary.md](decisions/ADR-0019-admin-console-and-governance-boundary.md) → [decisions/ADR-0021-ai-synchronized-cn-holiday-calendar.md](decisions/ADR-0021-ai-synchronized-cn-holiday-calendar.md) → [decisions/ADR-0022-data-collection-staging-and-relation-clues.md](decisions/ADR-0022-data-collection-staging-and-relation-clues.md) → [domain/地点数据来源与采集规范.md](domain/地点数据来源与采集规范.md) → [test/gate7-data-deployment-readiness-plan.md](test/gate7-data-deployment-readiness-plan.md) → [specs/data-model.md](specs/data-model.md) |
| 测试 / 验证 | [assumptions.md](assumptions.md) → [process/gates.md](process/gates.md) → [specs/](specs/) → [test/README.md](test/README.md) → [test/gate7-validation-plan.md](test/gate7-validation-plan.md) → [test/gate7-data-deployment-readiness-plan.md](test/gate7-data-deployment-readiness-plan.md) → [ops/gate7-controlled-h5-docker-deployment.md](ops/gate7-controlled-h5-docker-deployment.md) → [test/gate7-research-environment.md](test/gate7-research-environment.md) |

## 目录结构

```
docs/
  00-index.md            ← 你在这里（文档地图）
  assumptions.md         ★ 假设登记册（H1-H12，工作流账本）
  product/               产品全景、用户/管理功能架构、完整性审查、UI/交互和技术选型文档
  domain/                ★ 旅行领域规范（硬事实唯一来源，求解器与 LLM 都从这里读）
  decisions/             ADR 架构决策记录
  specs/                 需求规格 + Given/When/Then 验收标准
  research/              用户研究计划 + 结论
  test/                  测试方案 + Golden Cases + 验证报告
  ops/                   部署、外部 Provider、迁移与恢复操作说明
  process/               AI 协作开发 Gate、完整路线图、统一状态与任务协议
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

- 假设状态变更 → 更新 [assumptions.md](assumptions.md)
- 技术决策 → 新增 [decisions/](decisions/) 下的 ADR
- 领域规范变更 → 更新 [domain/](domain/) 并通知数据与求解器两方
- 管理身份、审核、发布或治理边界变更 → 更新 [product/管理端功能模块设计.md](product/管理端功能模块设计.md) 和对应 ADR/API/数据模型

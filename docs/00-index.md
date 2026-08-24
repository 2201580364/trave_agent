# 文档地图与阅读顺序

> 新人 / 新会话的入口。按角色选择阅读路径。

## 当前状态入口

任何新会话先读 [process/project-status.md](process/project-status.md)。该文件记录当前里程碑、正在进行的任务、已完成证据、未完成项和下一步。

## 按角色

| 角色 | 阅读顺序 |
|---|---|
| 产品 / 投资人 | [process/project-status.md](process/project-status.md) → [product/功能模块设计.md](product/功能模块设计.md) → [product/信息架构与UI设计.md](product/信息架构与UI设计.md) → [product/交互流程与状态机设计.md](product/交互流程与状态机设计.md) → [assumptions.md](assumptions.md) → [product/旅行助手产品文档.md](product/旅行助手产品文档.md) |
| 工程师（后端/求解器） | [assumptions.md](assumptions.md) → [product/M1 MVP技术选型文档.md](product/M1 MVP技术选型文档.md) → [domain/](domain/) |
| 工程师（数据） | [product/M1 MVP技术选型文档.md](product/M1 MVP技术选型文档.md) → [domain/开放时间数据规范.md](domain/开放时间数据规范.md) → [test/](test/) |
| 测试 / 验证 | [assumptions.md](assumptions.md) → [specs/](specs/) → [test/](test/) |

## 目录结构

```
docs/
  00-index.md            ← 你在这里（文档地图）
  assumptions.md         ★ 假设登记册（H1-H12，工作流账本）
  product/               产品文档、技术选型文档（来源，只读）
  domain/                ★ 旅行领域规范（硬事实唯一来源，求解器与 LLM 都从这里读）
  decisions/             ADR 架构决策记录
  specs/                 需求规格 + Given/When/Then 验收标准
  research/              用户研究计划 + 结论
  test/                  测试方案 + Golden Cases + 验证报告
  process/               AI 协作开发 Gate、权威来源与任务协议
```

## 命名约定

- `M1–M4`：产品路线里程碑；
- `P0–M2`：实现优先级；
- `G0–G7`：假设驱动开发 Gate；
- 冻结机器 ID 中的 `M1/M1` 为兼容性标识，不再作为产品阶段术语。

## 核心概念

- **假设（H-x）**：产品待验证的命题，是工作流的最小单位。任何工作都回溯到某个 H-x。
- **硬事实**：开放时间、闭馆日、价格等不可由 LLM 生成、只从结构化数据读取的信息。
- **硬约束**：必须满足、否则行程不成立的条件（开放时间、体力预算、时间锚点、闭馆日）。
- **Gate**：阶段退出准则，不满足不进下一阶段。

## 维护约定

- 假设状态变更 → 更新 [assumptions.md](assumptions.md)
- 技术决策 → 新增 [decisions/](decisions/) 下的 ADR
- 领域规范变更 → 更新 [domain/](domain/) 并通知数据与求解器两方

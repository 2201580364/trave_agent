# 文档地图与阅读顺序

> 新人 / 新会话的入口。按角色选择阅读路径。

## 按角色

| 角色 | 阅读顺序 |
|---|---|
| 产品 / 投资人 | [assumptions.md](assumptions.md) → [product/旅行助手产品文档.md](product/旅行助手产品文档.md) |
| 工程师（后端/求解器） | [assumptions.md](assumptions.md) → [product/P1 MVP技术选型文档.md](product/P1 MVP技术选型文档.md) → [domain/](domain/) |
| 工程师（数据） | [product/P1 MVP技术选型文档.md](product/P1 MVP技术选型文档.md) → [domain/开放时间数据规范.md](domain/开放时间数据规范.md) → [test/](test/) |
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
```

## 核心概念

- **假设（H-x）**：产品待验证的命题，是工作流的最小单位。任何工作都回溯到某个 H-x。
- **硬事实**：开放时间、闭馆日、价格等不可由 LLM 生成、只从结构化数据读取的信息。
- **硬约束**：必须满足、否则行程不成立的条件（开放时间、体力预算、时间锚点、闭馆日）。
- **Gate**：阶段退出准则，不满足不进下一阶段。

## 维护约定

- 假设状态变更 → 更新 [assumptions.md](assumptions.md)
- 技术决策 → 新增 [decisions/](decisions/) 下的 ADR
- 领域规范变更 → 更新 [domain/](domain/) 并通知数据与求解器两方

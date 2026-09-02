# 需求规格（Specs）

> 需求规格 = 功能 + **Given/When/Then 验收标准** + 可追溯的假设编号。
> 由 `/spec` 命令或 `spec` skill 从产品文档生成，G2 阶段产出。

## 文件约定

已稳定并版本化的求解器公开边界见 [solver-p1-contract.md](solver-p1-contract.md)。应用、API、数据库和页面设计必须依赖该契约，而不是直接依赖求解器内部实现细节。

M1 应用层规格已经完成 A5 同步，OM1 数据治理规格持续补充：

- [api-contract.md](api-contract.md) V2.9：已实现的用户 HTTP 能力，以及 OM1 管理身份/会话/RBAC/审核/发布端点和 O18 受控采集批次计划契约；
- [data-model.md](data-model.md) V3.0：持久化实体、事务、发布快照、Alembic 0001–0013 实际链；AdminActor/Role/Session/AuditEvent、审核任务、研究快照批次已实现，节假日历与采集批次模型仍待后续追加迁移；
- [O18 采集设计](../product/O18地点数据采集与关系识别设计.md)：采集来源、批次、归一/去重、关系线索和人工审核衔接的产品设计；
- [ADR-0022](../decisions/ADR-0022-data-collection-staging-and-relation-clues.md)：采集只进入 staging、AI 不越级、批次幂等和关系线索裁决边界。

旧 `/regenerate`、单一 `transport_type` 和单表 `trips.itinerary JSON` 不再是当前实现依据。

- 每个功能一篇，命名 `xxx.md`（如 `trip-solver.md`）。
- 头标含：关联假设（`H-x`）、关联指标、优先级。

## 验收标准模板

```
### 功能：一键生成分日行程（关联 H3、H7）

场景：用户选定 5 个景点、3 天、正常模式、周一到达
Given 某景点 close_days=[1]（周一闭馆）
When 求解器生成 Day 1（周一）行程
Then 该景点不出现在 Day 1
```

## 后续规格队列（按优先级）

1. `trip-solver.md` —— 一键生成分日行程（核心，承载 H3，最优先）
2. `attraction-browse.md` —— 景点列表 + 类型筛选
3. `transport-input.md` —— 大交通输入（关联 H6）
4. `trip-revision.md` —— 修改草稿后创建新 GenerationIntent 和 TripRevision；不使用含义模糊的 regenerate
5. `share-card.md` —— 行程分享卡片（关联 H11）
6. `feedback.md` —— 👍👎 反馈

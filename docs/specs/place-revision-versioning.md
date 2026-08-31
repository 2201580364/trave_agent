# 地点 Revision 版本化闭环

适用节点：`G7-R0.2-05-02`，OM1 地点审核工作台首版。

## 目标

地点事实不得原地覆盖已审核版本。管理侧的标准操作顺序是：

```text
新建修订版本 -> 修改 candidate -> 送审/重新审核 -> publication check -> 发布新 Projection 快照
```

## 操作契约

1. `POST /api/v1/admin/places/{place_id}/revisions` 接收 `base_revision_id`、`operation_intent_id` 和 reason 字段，从指定基线创建 `revision_number + 1` 的 `candidate`。基线 Revision、其审核时间和发布状态不改变。
2. `PATCH /api/v1/admin/place-revisions/{revision_id}` 必须携带 `expected_revision_number`，且目标必须是 `candidate`。编辑后清除 `reviewed_at`、`published_at`、`solver_eligible`、`conflicts_resolved`，并将 `relation_review_status` 重置为 `pending`，因此编辑后的版本必须重新完成 O07 检查并送审。
3. `POST /api/v1/admin/place-revisions/{revision_id}/review-tasks` 与审核决定接口复用现有审核事务和审计规则。审核通过后 Revision 进入 `human_verified`，并保留完整决定历史。
4. `GET /api/v1/admin/place-revisions/{revision_id}/publication-checks` 返回 `{publishable, reason_codes}`。`POST /api/v1/admin/place-revisions/{revision_id}/publications` 只有在依赖闭包通过时才允许执行。

## 幂等与错误

- 创建、编辑和发布按规范化载荷计算 operation digest；相同 intent、相同载荷重试返回原结果，不重复创建 Revision、审计或发布。
- 同一 intent 携带不同载荷返回 `409 admin_operation_intent_conflict`。
- 编辑版本过期返回 `409 review_task_conflict`（后续可拆分为专用 `place_revision_version_conflict`）。
- 发布门禁失败返回 `409 publication_gate_rejected`，并在 `details.reason_codes` 返回稳定机器码；Revision 与 Projection 状态保持不变。

## 发布边界

当前发布入口是 Projection 级能力：它把已通过门禁的 `SolverPlaceProjection` 和对应 Revision 标记为 `published`，返回 projection、Revision、数据快照版本和发布时间。它不等同于完整研究快照闭环。

以下能力仍属于 `R0.2-07`：独立 research snapshot 实体、内容哈希、城市当前快照指针、批次发布、批次逐项结果、旧快照退役和失败回滚。

新建 Revision 会复制基线 Revision 当前仍有效的几何、访问点、时间规则、闭馆日和日期例外证据，并为子记录生成新的 Revision 作用域 ID；复制后的证据统一重置为待核验，已停用证据不会重新生效。地点关系记录是 Place 级关系，不复制外键，但会在新 Revision 的证据视图中按当前 Place 重新加载。Projection 不复制，必须在新 Revision 完成审核后重新准备。发布检查仍会明确报告缺失依赖，禁止通过共享旧 Revision 外键绕过重新审核。

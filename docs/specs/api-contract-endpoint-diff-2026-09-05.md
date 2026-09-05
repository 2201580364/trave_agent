# api-contract.md 端点清单 vs 实际路由 差异清单

- 日期：2026-09-05
- 任务来源：transformation-plan S1.5-1 ②
- 对比对象：`docs/specs/api-contract.md`（V2.10 结构修复后）↔ `src/travel_agent/interfaces/http/app.py`（用户端）+ `admin.py`（管理端，prefix=`/api/v1/admin`）
- 用途：供人工裁决「补齐文档 / 补齐实现 / 删除契约」；本清单只登记事实，不做裁决。
- **裁决状态：已完成（2026-09-05，见第三节各条标注；契约已更新至 V2.11）**

## 一、用户端（app.py，prefix=/api/v1）

### 1.1 文档 §4 端点总览 20 条 ↔ 实现：19/20 一致

全部 §4 表内端点均已实现（含 plan-shares 三件套、feedback 两级、revisions 历史）。

### 1.2 文档有、实现无（Doc-only）

| 端点 | 文档位置 | 说明 |
|---|---|---|
| `POST /generation-intents/{intent_id}/retry` | §8.3，§4 标注 P1 | 契约明确为 M1 P1；无路由实现 |

### 1.3 实现有、文档端点总览缺登记

| 端点 | 实现位置 | 说明 |
|---|---|---|
| `POST /trips/{trip_id}/revisions/{revision_id}/attraction-replacements` | app.py:541 | 已在 §9.5 完整定义；本次已在 §4 表后补一行指引，不再算缺登记 |
| `GET /health/live`、`GET /health/ready` | app.py:281/285 | 基础设施探针；契约未写。建议裁决：作为运维约定写入 §2 或明确声明不属契约 |

## 二、管理端（admin.py，prefix=/api/v1/admin）

### 2.1 文档 §15.2 主表 29 行 ↔ 实现：26/29 一致

含 O05（holiday-calendars、holiday-exceptions）、O04 子资源（geometries / access-points 三件套、time-rules / closures / date-exceptions 三件套、逐项 evidence review）、O06 source-conflicts、O07 relations resolve/confirm-none、批量审核、发布链（publication-checks / projection-preparations / publications / batches / snapshots）、O17 五端点 + 日历详情/impact。

### 2.2 文档有、实现无（Doc-only）——重点裁决对象

| 端点 | 文档位置 | 说明 |
|---|---|---|
| `POST /api/v1/admin/candidates` | §15.2 主表 | 契约语义「创建最小候选，不伪造 human_verified」；无路由。与「创建候选 Revision」实际走 `POST /places/{place_id}/revisions` 的现状可能重复 |
| `GET /api/v1/admin/places/{place_id}` | §15.2 主表 | 「Place + 当前 Revision + 依赖摘要」聚合读；无路由。admin-web 当前靠 candidates / place-revisions/{id} 组合取数 |
| `POST /api/v1/admin/places/{place_id}/retirements` | §15.2 主表 | 独立退役端点无路由。注意：R0.2-07 的「发布新版原子退役旧版本」语义在 publications 链路内实现（c2ea117→89ea3de），与本端点是两回事；需裁决该端点改为「计划」还是补实现 |
| `GET /api/v1/admin/research-snapshots/{snapshot_id}` 下无差异 | — | （核对项，已实现） |

### 2.3 实现有、文档缺登记

| 端点 | 实现位置 | 说明 |
|---|---|---|
| `GET /api/v1/admin/holiday-calendar-sync-capability` | admin.py:419 | O17 前端能力探测（execution_available + region_code）；建议补入 §15.2 O17 小节 |
| `GET /api/v1/admin/dashboard-summary` | admin.py:1469 | OM1 工作台汇总；建议补入 §15.2 |
| `GET /api/v1/admin/place-revisions/{revision_id}` | admin.py:1482 | Revision 详情读（§15.2 只有 PATCH 该资源，无 GET）；建议补入主表 |

### 2.4 O18（§15.5）

8 条草案端点全部未实现——与文档「计划，当前代码尚未实现」声明一致，无漂移。

## 三、裁决建议（供下一轮人工确认，不改代码）

1. §8.3 retry（P1）→ ✅ 已裁决：保留契约，标注「未排期」（§4 表 + §8.3 均已注明无路由实现）。
2. `POST /admin/candidates` 与 `GET /admin/places/{place_id}` → ✅ 已裁决：candidates **删除**（与 `POST /places/{place_id}/revisions` 功能重复，契约只留唯一创建路径）；place 聚合读 **移入 §15.2.0「计划端点（未实现）」**（同 O18 模式）。
3. `retirements` 独立端点 → ✅ 已裁决：**删除端点**，§15.2 新增「发布版本退役语义」声明——退役由 publications 链路（单条 + 批次）发布新版时同事务原子完成，不提供绕过发布门禁的独立退役通道。
4. 三个未登记的已实现端点 → ✅ 已裁决：补入文档（`GET /place-revisions/{revision_id}` 入 §15.2 主表；`dashboard-summary` 入 §15.2 主表；`holiday-calendar-sync-capability` 入 O17 小节表）。
5. health 探针 → ✅ 已裁决：写入 §2.1.1「运维探针」。

> 裁决后契约状态：§4 用户端 19 条已实现 + retry（P1 未排期）；§15.2 管理端主表全部已实现（含补登 3 条）；计划端点集中在 §15.2.0（1 条）与 §15.5 O18（8 条）。

## 四、本次结构修复附带改动记录（api-contract.md）

1. 删除误插在 §4/§5 之间的「## 12. O09」整节（原第二个 ## 12）。
2. O09 内容回流为 §15.2 内 `#### O09 管理端研究快照批次`（语义不变，仅位置和层级）。
3. 无编号追加节编入 15.2 体系：`15.2.1 Revision 来源记录维护`、`15.2.2 O05 指定日期解析预览`、`15.2.3 O06 来源冲突只读面与裁决`（并入原散落的 source-conflicts 两段）、`15.2.4 批量审核与 O07 关系裁决`。
4. 文档版本头 V2.9 → V2.10。
5. `check_docs.py` 4 项检测全过；无外部文档按章节号引用本契约，重排无断链。

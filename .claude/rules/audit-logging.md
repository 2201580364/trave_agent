# 管理操作审计日志规范

**适用**：`application/admin/` 全部写用例，以及未来任何需要操作审计的接口族。制定于 2026-09-08 审计评审（评审结论：不引入切面/中间件，坚持领域层手工记录 + 同事务；本规范把已达成的一致做法制度化，消除三处三样的构造器/摘要/校验实现）。

## 一、核心纪律（不可协商）

1. **审计与业务同事务**：审计事件通过 `uow.audits.add(...)` 与业务变更共用同一个 UnitOfWork，由同一次 `uow.commit()` 原子落盘。禁止在 HTTP 层、中间件、装饰器或任何「请求后」位置另起事务写审计——会出现业务成功/审计失败（或反之）的分裂状态。
2. **审计构造必须经共享构造器**：禁止直接调用 `AdminAuditEvent(...)` 位置传参（17 个字段，加字段即错位）。统一使用 `application/admin/audit_events.py` 的 `build_audit_event(...)`（全关键字参数）。
3. **禁改历史**：`admin_audit_events` 是追加式（append-only）。不提供 UPDATE/DELETE 路径；纠错靠新事件，不靠改旧事件。
4. **不落敏感明文**：`reason_text` 过敏感词校验；`before/after_digest` 只存 SHA-256 摘要，不存原文快照。

## 二、事件字段语义

| 字段 | 语义 | 规则 |
|---|---|---|
| `action` | 稳定动作码 | 见第三节命名法；一经发布不得改写（客户端按码做中文映射） |
| `target_type` | 对象族 | 小写蛇形，登记于第四节 |
| `target_id` | 对象 ID | 不透明字符串 |
| `target_revision` | 涉及的 Revision 号 | 仅 Revision 类操作填 |
| `before/after_digest` | 变更前后状态摘要 | canonical JSON → SHA-256（第五节），只读操作不填 |
| `reason_code` | 稳定理由码 | `^[A-Z][A-Z0-9_]{2,63}$` |
| `reason_text` | 人类可读理由 | ≤500 字符、禁敏感词（密码/密钥/令牌等，中英文）、禁控制字符 |
| `request_id` | 请求贯穿 ID | 来自 `X-Request-ID` 中间件，响应头回带同值 |
| `operation_intent_id` + `operation_digest` | 幂等键与意图摘要 | 写操作必带（重放判定依据） |
| `result` | `succeeded` / `rejected` / `failed` | 拒绝也要记录（如 `ADMIN_LOGIN_REJECTED`） |
| `error_code` | 稳定错误码 | 仅失败时填 |
| `actor_role` | 记账角色 | 由调用方按业务语义选择（见第六节），不自动推断 |

## 三、动作码命名法与权威登记表

命名法：`<域前缀>_<对象>_<动作>`，大写蛇形。**新增动作码必须先在下表登记**（`tests/application/test_audit_registry.py` 会在测试期扫描代码，出现未登记码即失败）。登记表每行一个动作码（不得用 `/` 合并缩写，保证解析唯一性）。

| 动作码 | target_type | 语义 |
|---|---|---|
| ADMIN_ACTOR_BOOTSTRAPPED | admin_actor | 初始管理员引导 |
| ADMIN_ACTOR_CREATE | admin_actor | 创建管理员 |
| ADMIN_ACTOR_ROLES_CHANGE | admin_actor | 角色变更（expected version 乐观锁） |
| ADMIN_SESSION_CREATE | admin_session / admin_actor_login | 登录成功（target 为会话）与登录拒绝（target 为 actor） |
| ADMIN_SESSION_REVOKE | admin_session | 撤销会话 |
| PLACE_REVISION_CREATED | place_revision | 创建 candidate Revision |
| PLACE_REVISION_UPDATED | place_revision | 编辑 candidate |
| PLACE_REVISION_PUBLISHED | place_revision | 发布（含原子退役旧版） |
| PLACE_GEOMETRY_CREATED | place_revision | O04 几何子证据新增 |
| PLACE_GEOMETRY_UPDATED | place_revision | O04 几何子证据编辑 |
| PLACE_GEOMETRY_RETIRED | place_revision | O04 几何子证据停用 |
| PLACE_ACCESS_POINT_CREATED | place_revision | O04 访问点新增 |
| PLACE_ACCESS_POINT_UPDATED | place_revision | O04 访问点编辑 |
| PLACE_ACCESS_POINT_RETIRED | place_revision | O04 访问点停用 |
| PLACE_TIME_RULE_CREATED | place_revision | O05 时间规则新增 |
| PLACE_TIME_RULE_UPDATED | place_revision | O05 时间规则编辑 |
| PLACE_TIME_RULE_DELETED | place_time_rule | O05 候选修订时间规则删除（H3/C2），与停用保留记录区分 |
| PLACE_CLOSURE_CREATED | place_revision | O05 闭馆日新增 |
| PLACE_CLOSURE_UPDATED | place_revision | O05 闭馆日编辑 |
| PLACE_DATE_EXCEPTION_CREATED | place_revision | O05 日期例外新增 |
| PLACE_DATE_EXCEPTION_UPDATED | place_revision | O05 日期例外编辑 |
| PLACE_EVIDENCE_REVIEWED | place_revision | 子证据逐项审核 |
| PLACE_REVIEW_SUBMITTED | review_task | 送审（创建/重提任务） |
| PLACE_REVIEW_DECIDED | review_task | 审核决定（approve/request_changes/cancel） |
| PLACE_SOURCE_RECORD_CREATED | place_source_record | O06 来源记录挂接 |
| PLACE_SOURCE_RECORD_DETACHED | place_source_record | O06 来源记录解除 |
| PLACE_SOURCE_CONFLICTS_RESOLVED | place_revision | O06 来源冲突裁决 |
| PLACE_RELATION_RESOLUTION_UPDATED | place_revision | O07 关系裁决 |
| PLACE_RELATION_REVIEW_CONFIRMED_NONE | place_revision | O07 无关系确认 |
| PLACE_HOLIDAY_EXCEPTIONS_GENERATED | place_revision | O05 节假日例外物化 |
| SOLVER_PROJECTION_PREPARED | solver_projection | candidate Projection 准备 |
| PUBLICATION_BATCH_PREVIEWED | publication_batch | 批次预览 |
| PUBLICATION_BATCH_EXECUTED | publication_batch | 批次执行 |
| HOLIDAY_CALENDAR_SYNC_QUEUED | holiday_calendar_sync_job | 同步任务入队 |
| HOLIDAY_CALENDAR_SYNC_CANCELLED | holiday_calendar_sync_job | 同步任务取消 |
| HOLIDAY_CALENDAR_SYNC_TEMPORARILY_UNAVAILABLE | holiday_calendar_sync_job | Worker 不可用（terminal action） |
| HOLIDAY_CALENDAR_SYNC_NEEDS_ATTENTION | holiday_calendar_sync_job | 需人工介入（terminal action） |
| HOLIDAY_CALENDAR_NOT_ANNOUNCED | holiday_calendar_sync_job | 官方未发公告（terminal action） |
| HOLIDAY_CALENDAR_UP_TO_DATE | holiday_calendar_sync_job | 已是最新（terminal action） |
| HOLIDAY_CALENDAR_PREVIEW_CONFIRMED | holiday_calendar | 预览确认发布 |
| HOLIDAY_CALENDAR_PUBLISHED | holiday_calendar | 日历版本发布 |

| HOLIDAY_CALENDAR_PREVIEW_VALIDATED | holiday_calendar | 预览校验完成（terminal action，`_terminal_audit_fields` validated_preview 分支） |

**O17 reason_code（同模块，与 action 区分，不作 action 登记以保持测试双射）**：`HOLIDAY_SYNC_CANCELLED`、`HOLIDAY_CALENDAR_SYNC_REQUESTED`、`HOLIDAY_CALENDAR_VALIDATED`、`HOLIDAY_CALENDAR_VALIDATION_FAILED`、`HOLIDAY_CALENDAR_PREVIEW_ONLY`、`HOLIDAY_CALENDAR_CONTENT_UNCHANGED`、`OFFICIAL_ANNOUNCEMENT_NOT_FOUND`、`OFFICIAL_SOURCE_UNAVAILABLE`。

## 四、target_type 登记表

`admin_actor`、`admin_actor_login`、`admin_session`、`place_revision`、`place_source_record`、`place_relation`、`place_time_rule`、`review_task`、`publication_batch`、`solver_projection`、`holiday_calendar`、`holiday_calendar_sync_job`。新增 target_type 同样先登记本行。

## 五、摘要哈希（唯一实现）

`application/admin/audit_events.py::canonical_digest(value) -> str`：`json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))` → SHA-256 hexdigest。全仓唯一的 canonical 摘要实现；`service.py`/`review.py`/`holiday_calendar_sync.py` 的同名私有函数已删除并改引此处。注意：*_token_hash、client_ip/user_agent 脱敏哈希是**安全哈希**（哈希原文本身），不走 canonical JSON，不归本规范管。

## 六、actor_role 记账规则

由调用方按**业务语义**显式传入，不做通用推断：

- 审核/数据流（review.py 系）：按 `data_reviewer > admin_security > data_editor > data_publisher` 优先取，兜底 `authenticated_admin`；
- 身份/安全流（service.py 系）：按 `admin_security > data_publisher > data_reviewer > data_editor > research_viewer > content_moderator` 优先取，兜底 `authenticated_admin`；
- 登录失败事件固定 `unauthenticated`。

两套优先级顺序不同是**有意的语义差异**，不得为了「统一」而合并。

## 七、新增审计端点 checklist

1. 动作码/目标族在第三、四节登记 → 测试才有保护；
2. 用例方法内 `uow.audits.add(build_audit_event(...))`，与业务同 `uow.commit()`；
3. `reason_code`/`reason_text` 走 `validate_audit_reason(...)`（同在 audit_events.py）；
4. 拒绝路径也要记事件（`result="rejected"`）；
5. 重放安全：写操作带 `operation_intent_id`，同 intent 重放不产生重复事件；
6. 契约同步：端点语义进 api-contract.md 时提及审计动作码。

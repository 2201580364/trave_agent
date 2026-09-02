# M1 业务数据与 OM1 管理逻辑数据模型

- 文档版本：V3.0
- 日期：2026-09-02
- 阶段：A6 首个浏览器可操作纵向切片
- 状态：SQLAlchemy 仓储与 Alembic 0001–0013 已实现；0006–0013 已覆盖通用地点目录、管理身份与审计、审核工作流、Revision 审核标记/乐观锁、研究快照批次、关系检查和历史求解资格回填。16.6 节假日历同步持久化模型仍是 G7-R0.2-09 计划，不得写成已迁移。服务器真实 MySQL 当前保持既有受控基线，后续迁移须在 R0.3 备份后统一执行；本机不安装或启动 MySQL/Redis
- 数据库：MySQL 8.0；SQLAlchemy 2.0；Alembic
- 上游：API 契约 V2.9、应用代码架构 V1.4、ADR-0002、ADR-0005、ADR-0009、ADR-0018、ADR-0019、ADR-0021、ADR-0022

## 1. 建模目标与原则

模型必须可靠表达：

```text
主体
→ 可恢复且有版本的草稿
→ 一次幂等生成意图
→ 一次可审计求解运行
→ 一个不可变 TripRevision
→ Trip 当前版本和历史版本
```

M1 不再使用单个 `trips.itinerary JSON` 同时承担草稿、当前结果、历史、失败任务和分享状态。

原则：

1. 业务 ID 使用应用生成的不透明字符串，推荐 ULID/UUID；
2. 时间戳保存 UTC，业务日期和钟点按目的地时区解释；
3. TripRevision、生成输入快照和 SolverRun 创建后不可原地修改；
4. 草稿用乐观锁，GenerationIntent 用唯一键和输入哈希实现幂等；
5. 求解期间不持有数据库事务，完成结果在短事务中提交；
6. 只有已发布且一致的数据快照能进入生成；
7. 关系化保存身份、状态、版本、唯一键和索引，完整输入/结果可保存为带版本的不可变 JSON；
8. token 只保存带算法版本的不可逆摘要；
9. JSON 字段必须有 Schema 版本，不能作为无结构杂物箱；
10. M2–M4 实体不提前创建空表。

## 2. 实体关系

```text
principals
├── anonymous_credentials
├── trip_drafts
│   └── generation_intents
│       ├── solver_runs
│       └── trip_revisions
└── trips
    └── trip_revisions

cities
├── attractions
│   ├── attraction_time_rules
│   ├── attraction_weekly_closures
│   ├── attraction_date_exceptions
│   └── attraction_revisions
└── published_data_snapshots
    ├── published_snapshot_attractions
    ├── weather_snapshot_days
    └── od_snapshot_entries
```

## 3. 公共字段约定

| 字段 | 类型建议 | 规则 |
|---|---|---|
| `*_id` | `VARCHAR(32)` | 应用生成，不依赖自增 ID 暴露顺序 |
| `created_at/updated_at` | `DATETIME(6)` | UTC；应用层统一 Clock |
| `version` | `BIGINT UNSIGNED` | 从 1 递增；乐观锁条件的一部分 |
| 状态/枚举 | `VARCHAR(40)` | 应用 Enum 校验；必要时数据库 CHECK，不使用难迁移的 MySQL ENUM |
| snapshot | `JSON` | 表字段或内容必须声明 schema version |
| hash | `CHAR(64)` | 规范化 JSON 的 SHA-256 十六进制 |

敏感 token 使用带 pepper HMAC 或等价方案保存摘要，并记录 `hash_version`；不直接保存原值。

## 4. 身份与匿名访问

### 4.1 `principals`

统一匿名主体和未来账号主体，避免登录绑定时迁移全部业务外键。

```sql
CREATE TABLE principals (
    principal_id VARCHAR(32) PRIMARY KEY,
    principal_type VARCHAR(20) NOT NULL,          -- anonymous | user
    status VARCHAR(20) NOT NULL,                  -- active | expired | disabled
    user_id VARCHAR(32) NULL,
    created_at DATETIME(6) NOT NULL,
    updated_at DATETIME(6) NOT NULL,
    expires_at DATETIME(6) NULL,
    CONSTRAINT uq_principal_user UNIQUE (user_id)
);
```

### 4.2 `anonymous_credentials`

```sql
CREATE TABLE anonymous_credentials (
    credential_id VARCHAR(32) PRIMARY KEY,
    principal_id VARCHAR(32) NOT NULL,
    token_hash VARBINARY(64) NOT NULL,
    hash_version VARCHAR(20) NOT NULL,
    status VARCHAR(20) NOT NULL,                  -- active | revoked | expired
    created_at DATETIME(6) NOT NULL,
    expires_at DATETIME(6) NOT NULL,
    last_used_at DATETIME(6) NULL,
    CONSTRAINT uq_anonymous_token_hash UNIQUE (token_hash),
    CONSTRAINT fk_credential_principal FOREIGN KEY (principal_id)
        REFERENCES principals(principal_id)
);

CREATE INDEX ix_anonymous_credentials_principal_status
ON anonymous_credentials(principal_id, status);
```

## 5. 城市与景点工作数据

### 5.1 `cities`

```sql
CREATE TABLE cities (
    city_id VARCHAR(32) PRIMARY KEY,
    name VARCHAR(80) NOT NULL,
    province VARCHAR(80) NULL,
    timezone VARCHAR(64) NOT NULL,
    center_lat DECIMAL(10,7) NULL,
    center_lng DECIMAL(10,7) NULL,
    status VARCHAR(20) NOT NULL,
    created_at DATETIME(6) NOT NULL,
    updated_at DATETIME(6) NOT NULL
);
```

M1 只发布杭州，但不能在代码中用城市名称绕过发布状态。

### 5.2 `attractions`

```sql
CREATE TABLE attractions (
    attraction_id VARCHAR(32) PRIMARY KEY,
    city_id VARCHAR(32) NOT NULL,
    name VARCHAR(120) NOT NULL,
    category VARCHAR(40) NOT NULL,
    energy_level TINYINT UNSIGNED NOT NULL,
    suggested_duration_min SMALLINT UNSIGNED NOT NULL,
    is_indoor BOOLEAN NOT NULL,
    is_always_open BOOLEAN NOT NULL DEFAULT FALSE,
    lat DECIMAL(10,7) NOT NULL,
    lng DECIMAL(10,7) NOT NULL,
    suitable_crowd JSON NULL,
    best_season JSON NULL,
    tags JSON NULL,
    data_source VARCHAR(80) NOT NULL,
    fetched_at DATETIME(6) NULL,
    data_verified BOOLEAN NOT NULL DEFAULT FALSE,
    conflict BOOLEAN NOT NULL DEFAULT FALSE,
    status VARCHAR(20) NOT NULL,                  -- active | inactive
    row_version BIGINT UNSIGNED NOT NULL DEFAULT 1,
    created_at DATETIME(6) NOT NULL,
    updated_at DATETIME(6) NOT NULL,
    CONSTRAINT fk_attraction_city FOREIGN KEY (city_id) REFERENCES cities(city_id),
    CONSTRAINT ck_attraction_energy CHECK (energy_level BETWEEN 1 AND 5),
    CONSTRAINT ck_attraction_duration CHECK (suggested_duration_min > 0),
    CONSTRAINT uq_attraction_city_name UNIQUE (city_id, name)
);
```

`data_verified=true AND conflict=false AND status=active` 是发布必要条件，但还需通过时间规则、天气和 OD 一致性门禁。

#### G7-R0.2-03 已实现：通用地点目录物理模型

当前 `attractions` 继续只服务点状景点和 7 点历史技术基线。ADR-0018 的通用地点事实模型已由 `place_catalog` 领域模块、SQLAlchemy 映射和 Alembic `0006_place_catalog` 实现，不反向改写旧求解器事实：

```text
places
├── place_source_records
├── place_revisions
│   ├── place_geometries
│   ├── place_access_points
│   ├── place_time_rules
│   ├── place_closures
│   └── place_date_exceptions
├── place_relations
├── selection_exclusion_groups
│   └── selection_exclusion_members
└── solver_place_projections
```

物理模型和约束覆盖：

- `place_kind`：attraction/scenic_area/neighborhood/walking_route/market/show/experience；
- `geometry_kind`：point/area/route；
- `PlaceSourceRecord` 强制绑定 source、registry/dictionary ID 与规范化 SHA-256、来源 URL、采集方式、来源决策和目标阶段；conditional 来源在领域构造阶段即拒绝 `target_stage=published`；
- `PlaceRevision` 使用 `(place_id, revision_number)` 唯一约束，保存名称、类型、几何类型、时长范围、内部步行、体力、室内外、适用时段、人群、雨天适配、来源闭包和 candidate/human_verified/published/retired 生命周期；
- 几何、访问点、时间规则、闭馆日和日期例外分别持久化，访问点坐标使用 `DECIMAL(10,7)`，跨午夜分钟值允许到 2880；
- O05 Revision evidence 已覆盖 `place_time_rules`、`place_closures` 和 `place_date_exceptions`：三类记录严格按 `place_revision_id` 加载，其来源纳入当前 Place 的依赖闭包，并逐项暴露来源有效性、审核状态、active 状态和审核时间；candidate CRUD、软停用、重新启用和 reviewer 逐项审核已开放，指定日期解析预览仍待后续切片；
- `PlaceRelation` 表达 contains/part_of/overlaps/same_experience，并保存 pending/resolved/not_required 裁决状态；互斥组与成员使用独立表和唯一约束。`PlaceRevision.relation_review_status` 记录本次修订是否已完成关系检查：`pending`、`no_relations`；历史修订默认 `not_required` 以保持向后兼容。无关系时必须通过 O07 确认接口登记 `no_relations`，不得伪造关系行；
- `SolverPlaceProjection` 在同一 `data_snapshot_version` 内约束 solver node ID 唯一、PlaceRevision 唯一，保存显式到达/离开访问点、时长范围、solver payload 和稳定 SHA-256；
- 仓储拒绝直接插入 published Revision 或 projection；唯一发布入口加载 Place、Revision、来源、几何、访问点、时间和关系依赖闭包，执行 fail-closed 门禁后在同一事务中更新 Revision 与 projection 状态。

投影的有向路网端点固定为 `origin.departure_access_point → destination.arrival_access_point`。M1 中一个用户可选 Place 最多投影为一个 solver 节点；路线内部步行计入游览时长，不重复计入节点间 OD。现有 API `attraction_id` 在 M1 暂时承载稳定 `place_id` 作为兼容别名，不能用其字段名反推事实类型。

当前实施边界：

- 0001–0005 历史迁移未修改，0006 只新增表、索引、唯一约束和外键；
- 不把区域中心点当作 human_verified 游客入口；
- 不把 raw/candidate 爬取记录直接写入 published snapshot；
- 现有 `attractions`、7 点 JSON published snapshot 和历史 TripRevision 不迁移、不覆盖、不重算；
- R0.2-03 只提供事实与发布边界，尚未采集杭州 50–75 个研究地点，也尚未生成 immutable research snapshot；这些分别属于 R0.2-04～07。

### 5.3 `attraction_time_rules`

```sql
CREATE TABLE attraction_time_rules (
    time_rule_id VARCHAR(32) PRIMARY KEY,
    attraction_id VARCHAR(32) NOT NULL,
    start_month TINYINT UNSIGNED NOT NULL,
    start_day TINYINT UNSIGNED NOT NULL,
    end_month TINYINT UNSIGNED NOT NULL,
    end_day TINYINT UNSIGNED NOT NULL,
    open_min SMALLINT UNSIGNED NOT NULL,
    close_min SMALLINT UNSIGNED NOT NULL,          -- 跨午夜可 >1440，最大 2880
    last_entry_min SMALLINT UNSIGNED NULL,
    priority SMALLINT NOT NULL DEFAULT 0,
    source_ref VARCHAR(160) NOT NULL,
    fetched_at DATETIME(6) NULL,
    data_verified BOOLEAN NOT NULL DEFAULT FALSE,
    conflict BOOLEAN NOT NULL DEFAULT FALSE,
    status VARCHAR(20) NOT NULL,
    created_at DATETIME(6) NOT NULL,
    updated_at DATETIME(6) NOT NULL,
    CONSTRAINT fk_time_rule_attraction FOREIGN KEY (attraction_id)
        REFERENCES attractions(attraction_id),
    CONSTRAINT ck_time_rule_open CHECK (open_min < 1440),
    CONSTRAINT ck_time_rule_close CHECK (close_min > open_min AND close_min <= 2880),
    CONSTRAINT ck_time_rule_last_entry CHECK (
        last_entry_min IS NULL OR
        (last_entry_min >= open_min AND last_entry_min <= close_min)
    )
);
```

发布时同一景点同一日期只能解析出一个有效规则；priority 不能静默覆盖同级冲突。

### 5.4 多闭馆日和日期例外

```sql
CREATE TABLE attraction_weekly_closures (
    attraction_id VARCHAR(32) NOT NULL,
    iso_weekday TINYINT UNSIGNED NOT NULL,
    PRIMARY KEY (attraction_id, iso_weekday),
    CONSTRAINT fk_weekly_closure_attraction FOREIGN KEY (attraction_id)
        REFERENCES attractions(attraction_id),
    CONSTRAINT ck_iso_weekday CHECK (iso_weekday BETWEEN 1 AND 7)
);

CREATE TABLE attraction_date_exceptions (
    exception_id VARCHAR(32) PRIMARY KEY,
    attraction_id VARCHAR(32) NOT NULL,
    exception_date DATE NOT NULL,
    exception_type VARCHAR(20) NOT NULL,           -- open | closed
    time_rule_override JSON NULL,
    source_ref VARCHAR(160) NOT NULL,
    data_verified BOOLEAN NOT NULL DEFAULT FALSE,
    conflict BOOLEAN NOT NULL DEFAULT FALSE,
    created_at DATETIME(6) NOT NULL,
    updated_at DATETIME(6) NOT NULL,
    CONSTRAINT fk_date_exception_attraction FOREIGN KEY (attraction_id)
        REFERENCES attractions(attraction_id),
    CONSTRAINT uq_attraction_exception_date UNIQUE (attraction_id, exception_date)
);
```

具体日期例外替代不可执行的自由文本 `close_day_exception`。同一日期不能同时 open/closed。

### 5.5 `attraction_revisions`

```sql
CREATE TABLE attraction_revisions (
    attraction_revision_id VARCHAR(32) PRIMARY KEY,
    attraction_id VARCHAR(32) NOT NULL,
    revision_no BIGINT UNSIGNED NOT NULL,
    changed_by_principal_id VARCHAR(32) NULL,
    change_type VARCHAR(40) NOT NULL,
    before_snapshot JSON NULL,
    after_snapshot JSON NOT NULL,
    source_ref VARCHAR(160) NOT NULL,
    review_status VARCHAR(20) NOT NULL,
    created_at DATETIME(6) NOT NULL,
    CONSTRAINT fk_attraction_revision_attraction FOREIGN KEY (attraction_id)
        REFERENCES attractions(attraction_id),
    CONSTRAINT uq_attraction_revision_no UNIQUE (attraction_id, revision_no)
);
```

硬事实修改不能只覆盖当前值而不留 revision。

## 6. 发布数据快照

### 6.1 `published_data_snapshots`

```sql
CREATE TABLE published_data_snapshots (
    data_snapshot_version VARCHAR(80) PRIMARY KEY,
    city_id VARCHAR(32) NOT NULL,
    status VARCHAR(20) NOT NULL,                  -- building | published | retired | failed
    attraction_schema_version VARCHAR(30) NOT NULL,
    weather_version VARCHAR(80) NOT NULL,
    od_version VARCHAR(80) NOT NULL,
    od_basis VARCHAR(20) NOT NULL,                -- gaode | approximate
    created_by_principal_id VARCHAR(32) NULL,
    published_at DATETIME(6) NULL,
    validation_report JSON NOT NULL,
    content_hash CHAR(64) NOT NULL,
    created_at DATETIME(6) NOT NULL,
    CONSTRAINT fk_snapshot_city FOREIGN KEY (city_id) REFERENCES cities(city_id),
    CONSTRAINT uq_snapshot_content_hash UNIQUE (content_hash)
);

CREATE TABLE city_data_publications (
    city_id VARCHAR(32) PRIMARY KEY,
    current_snapshot_version VARCHAR(80) NOT NULL,
    updated_at DATETIME(6) NOT NULL,
    CONSTRAINT fk_publication_city FOREIGN KEY (city_id) REFERENCES cities(city_id),
    CONSTRAINT fk_publication_snapshot FOREIGN KEY (current_snapshot_version)
        REFERENCES published_data_snapshots(data_snapshot_version)
);
```

原子切换城市当前快照指针，避免并发扫描 `status=published` 判断当前版本。

### 6.2 不可变景点、天气和 OD 快照

```sql
CREATE TABLE published_snapshot_attractions (
    data_snapshot_version VARCHAR(80) NOT NULL,
    attraction_id VARCHAR(32) NOT NULL,
    attraction_snapshot JSON NOT NULL,
    attraction_snapshot_hash CHAR(64) NOT NULL,
    PRIMARY KEY (data_snapshot_version, attraction_id),
    CONSTRAINT fk_snapshot_attraction_version FOREIGN KEY (data_snapshot_version)
        REFERENCES published_data_snapshots(data_snapshot_version)
);

CREATE TABLE weather_snapshot_days (
    weather_version VARCHAR(80) NOT NULL,
    city_id VARCHAR(32) NOT NULL,
    weather_date DATE NOT NULL,
    basis VARCHAR(20) NOT NULL,                   -- forecast | climate
    severity VARCHAR(20) NOT NULL,                -- normal | advisory | extreme
    condition_code VARCHAR(40) NULL,
    source_ref VARCHAR(160) NOT NULL,
    fetched_at DATETIME(6) NOT NULL,
    PRIMARY KEY (weather_version, city_id, weather_date)
);

CREATE TABLE od_snapshot_entries (
    od_version VARCHAR(80) NOT NULL,
    origin_id VARCHAR(32) NOT NULL,
    destination_id VARCHAR(32) NOT NULL,
    travel_min SMALLINT UNSIGNED NOT NULL,
    basis VARCHAR(20) NOT NULL,
    source_ref VARCHAR(160) NOT NULL,
    fetched_at DATETIME(6) NOT NULL,
    PRIMARY KEY (od_version, origin_id, destination_id),
    CONSTRAINT ck_od_nonzero CHECK (
        (origin_id = destination_id AND travel_min = 0) OR
        (origin_id <> destination_id AND travel_min > 0)
    )
);
```

历史生成依赖发布快照而不是 attractions 当前工作行。A→B 与 B→A 独立，缺失边不能用 0 补齐。

#### G7-R0.2 计划演进：按需 OD 子图（尚未实现）

`od_snapshot_entries` 当前完整矩阵模型适用于 7 点 42/42 技术快照。扩大到 40–75 个研究地点后，不能默认要求全城、多模式 N² 预计算。计划新增或扩展以下概念：

```text
od_route_cache
od_subgraph_snapshots
od_subgraph_entries
solver_run_od_binding
```

每次求解只为实际选择、到离锚点和必要替换候选加载/获取有向 OD，并将实际使用的子图、来源、版本和 hash 绑定到 SolverRun/TripRevision。缓存不是历史事实来源；历史回放必须读取不可变子图快照。近似降级继续显式保存 basis/reason，缺失边不得写成 0。

该模型演进完成前，大规模地点目录不能直接接入当前要求完整有向矩阵的 `JsonPublishedSolverDataProvider`。

### 6.3 `visit_period_preferences`

```sql
CREATE TABLE visit_period_preferences (
    preference_id VARCHAR(32) PRIMARY KEY,
    attraction_id VARCHAR(32) NOT NULL,
    preferred_bucket VARCHAR(20) NOT NULL,
    acceptable_buckets JSON NOT NULL,
    source VARCHAR(40) NOT NULL,                  -- curated | public_guide_synthesis
    source_ref VARCHAR(160) NOT NULL,
    preference_version VARCHAR(80) NOT NULL,
    status VARCHAR(20) NOT NULL,
    created_at DATETIME(6) NOT NULL,
    CONSTRAINT fk_visit_preference_attraction FOREIGN KEY (attraction_id)
        REFERENCES attractions(attraction_id),
    CONSTRAINT uq_visit_preference_source UNIQUE (
        attraction_id, source, preference_version
    )
);
```

用户覆盖项随草稿 input snapshot 保存，不写入策展表。应用按 `user > curated > public_guide_synthesis` 合并，同级冲突不按插入顺序覆盖。

## 7. 草稿

### 7.1 `trip_drafts`

```sql
CREATE TABLE trip_drafts (
    draft_id VARCHAR(32) PRIMARY KEY,
    principal_id VARCHAR(32) NOT NULL,
    city_id VARCHAR(32) NOT NULL,
    status VARCHAR(20) NOT NULL,                  -- editing | needs_review | submitted | abandoned
    draft_version BIGINT UNSIGNED NOT NULL DEFAULT 1,
    start_date DATE NULL,
    end_date DATE NULL,
    arrival_transport_type VARCHAR(30) NULL,
    arrival_confirmation VARCHAR(40) NOT NULL DEFAULT 'unresolved',
    arrival_at DATETIME(6) NULL,
    station_to_city_min SMALLINT UNSIGNED NULL,
    station_to_city_source VARCHAR(40) NULL,
    station_to_city_confirmation VARCHAR(40) NULL,
    departure_transport_type VARCHAR(30) NULL,
    departure_confirmation VARCHAR(40) NOT NULL DEFAULT 'unresolved',
    departure_at DATETIME(6) NULL,
    station_early_min SMALLINT UNSIGNED NULL,
    station_early_source VARCHAR(40) NULL,
    last_visit_to_station_min SMALLINT UNSIGNED NULL,
    last_visit_to_station_source VARCHAR(40) NULL,
    travel_mode VARCHAR(20) NOT NULL DEFAULT 'normal',
    crowd_type VARCHAR(30) NOT NULL DEFAULT 'unspecified',
    selected_attraction_ids JSON NOT NULL,
    user_visit_period_preferences JSON NOT NULL,
    advanced_settings JSON NOT NULL,
    last_reviewed_data_snapshot_version VARCHAR(80) NULL,
    created_at DATETIME(6) NOT NULL,
    updated_at DATETIME(6) NOT NULL,
    abandoned_at DATETIME(6) NULL,
    CONSTRAINT fk_draft_principal FOREIGN KEY (principal_id)
        REFERENCES principals(principal_id),
    CONSTRAINT fk_draft_city FOREIGN KEY (city_id) REFERENCES cities(city_id),
    CONSTRAINT ck_draft_date_order CHECK (
        start_date IS NULL OR end_date IS NULL OR start_date <= end_date
    )
);

CREATE INDEX ix_trip_drafts_principal_status_updated
ON trip_drafts(principal_id, status, updated_at);
```

M1 选择集合通常 7–20 项，保存为规范化 JSON 以支持完整 PUT 替换和稳定哈希。出现跨草稿统计、单项并发编辑或大集合需求时再拆关联表。

乐观锁：

```sql
UPDATE trip_drafts
SET ..., draft_version = draft_version + 1, updated_at = :now
WHERE draft_id = :draft_id
  AND principal_id = :principal_id
  AND draft_version = :expected_version;
```

影响行数为 0 时区分不存在和版本冲突；未授权主体统一返回 404。

## 8. Trip、Intent、SolverRun 与 Revision

### 8.1 `trips`

```sql
CREATE TABLE trips (
    trip_id VARCHAR(32) PRIMARY KEY,
    principal_id VARCHAR(32) NOT NULL,
    city_id VARCHAR(32) NOT NULL,
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    status VARCHAR(20) NOT NULL,                  -- active | archived | deleted
    current_revision_id VARCHAR(32) NULL,
    created_at DATETIME(6) NOT NULL,
    updated_at DATETIME(6) NOT NULL,
    CONSTRAINT fk_trip_principal FOREIGN KEY (principal_id) REFERENCES principals(principal_id),
    CONSTRAINT fk_trip_city FOREIGN KEY (city_id) REFERENCES cities(city_id),
    CONSTRAINT ck_trip_dates CHECK (start_date <= end_date)
);

CREATE INDEX ix_trips_principal_updated
ON trips(principal_id, updated_at);
```

`current_revision_id` 外键在 trip_revisions 创建后通过后续迁移添加，避免建表环依赖。

### 8.2 `generation_intents`

```sql
CREATE TABLE generation_intents (
    generation_intent_id VARCHAR(32) PRIMARY KEY,
    principal_id VARCHAR(32) NOT NULL,
    draft_id VARCHAR(32) NOT NULL,
    draft_version BIGINT UNSIGNED NOT NULL,
    status VARCHAR(30) NOT NULL,
    input_schema_version VARCHAR(30) NOT NULL,
    input_snapshot JSON NOT NULL,
    input_snapshot_hash CHAR(64) NOT NULL,
    data_snapshot_version VARCHAR(80) NOT NULL,
    random_seed BIGINT NOT NULL,
    retry_count SMALLINT UNSIGNED NOT NULL DEFAULT 0,
    claimed_by VARCHAR(80) NULL,
    claimed_at DATETIME(6) NULL,
    failure_code VARCHAR(80) NULL,
    failure_details JSON NULL,
    trip_id VARCHAR(32) NULL,
    revision_id VARCHAR(32) NULL,
    target_trip_id VARCHAR(32) NULL,
    base_revision_id VARCHAR(32) NULL,
    submitted_at DATETIME(6) NOT NULL,
    started_at DATETIME(6) NULL,
    completed_at DATETIME(6) NULL,
    updated_at DATETIME(6) NOT NULL,
    CONSTRAINT fk_intent_principal FOREIGN KEY (principal_id)
        REFERENCES principals(principal_id),
    CONSTRAINT fk_intent_draft FOREIGN KEY (draft_id) REFERENCES trip_drafts(draft_id),
    CONSTRAINT fk_intent_data_snapshot FOREIGN KEY (data_snapshot_version)
        REFERENCES published_data_snapshots(data_snapshot_version)
);

CREATE INDEX ix_generation_intents_principal_submitted
ON generation_intents(principal_id, submitted_at);

CREATE INDEX ix_generation_intents_status_submitted
ON generation_intents(status, submitted_at);
```

主键保证业务幂等。收到相同 ID 时应用先读取已有记录，比较主体、draft ID 和 draft version；一致则直接返回原状态，不重新选择当前数据快照。首次创建后 `input_snapshot_hash` 用于回放和防篡改。不能仅因两个不同 intent 哈希相同就强制合并用户动作。

首次生成时 `target_trip_id/base_revision_id` 均为空；用户从现有行程发起景点替换等修订时两者必须同时存在。完成事务通过 `UPDATE trips ... WHERE trip_id=:id AND current_revision_id=:base_revision_id` 条件更新当前指针；只有影响一行的发布者可以继续创建 `base.revision_no + 1`，不相等时以 `trip_revision_conflict` 终止，旧版本继续可用。

原子领取：

```sql
UPDATE generation_intents
SET status='running', claimed_by=:worker, claimed_at=:now,
    started_at=COALESCE(started_at, :now), updated_at=:now
WHERE generation_intent_id=:id
  AND status IN ('queued', 'failed_retryable');
```

只有影响 1 行的执行者可以调用求解器。

### 8.3 `solver_runs`

```sql
CREATE TABLE solver_runs (
    solve_run_id VARCHAR(32) PRIMARY KEY,
    generation_intent_id VARCHAR(32) NOT NULL,
    run_no SMALLINT UNSIGNED NOT NULL,
    solver_version VARCHAR(80) NOT NULL,
    contract_version VARCHAR(80) NOT NULL,
    constraint_version VARCHAR(80) NOT NULL,
    parameter_version VARCHAR(80) NOT NULL,
    input_snapshot_hash CHAR(64) NOT NULL,
    data_snapshot_version VARCHAR(80) NOT NULL,
    od_basis VARCHAR(20) NOT NULL,
    weather_basis VARCHAR(20) NOT NULL,
    random_seed BIGINT NOT NULL,
    duration_ratio DECIMAL(5,4) NOT NULL,
    status VARCHAR(30) NOT NULL,
    input_count INT UNSIGNED NOT NULL,
    scheduled_count INT UNSIGNED NOT NULL,
    unplaced_count INT UNSIGNED NOT NULL,
    data_rejected_count INT UNSIGNED NOT NULL,
    hard_constraint_violations INT UNSIGNED NOT NULL,
    search_attempt_count INT UNSIGNED NOT NULL,
    timed_out_day_count INT UNSIGNED NOT NULL,
    best_so_far_day_count INT UNSIGNED NOT NULL,
    no_solution_day_count INT UNSIGNED NOT NULL,
    elapsed_ms INT UNSIGNED NOT NULL,
    decision_trace_schema_version VARCHAR(30) NOT NULL,
    decision_trace JSON NOT NULL,
    created_at DATETIME(6) NOT NULL,
    CONSTRAINT fk_solver_run_intent FOREIGN KEY (generation_intent_id)
        REFERENCES generation_intents(generation_intent_id),
    CONSTRAINT uq_solver_run_no UNIQUE (generation_intent_id, run_no),
    CONSTRAINT ck_solver_accounting CHECK (
        input_count = scheduled_count + unplaced_count + data_rejected_count
    )
);
```

稳定重试可产生新 `run_no`，但必须沿用完整回放键。失败 run 也保留；只有最终被接纳的 run 关联 TripRevision。

### 8.4 `trip_revisions`

```sql
CREATE TABLE trip_revisions (
    revision_id VARCHAR(32) PRIMARY KEY,
    trip_id VARCHAR(32) NOT NULL,
    revision_no BIGINT UNSIGNED NOT NULL,
    generation_intent_id VARCHAR(32) NOT NULL,
    solve_run_id VARCHAR(32) NOT NULL,
    completion_kind VARCHAR(30) NOT NULL,         -- complete_success | partial_success
    has_soft_degradation BOOLEAN NOT NULL,
    input_schema_version VARCHAR(30) NOT NULL,
    input_snapshot JSON NOT NULL,
    result_schema_version VARCHAR(30) NOT NULL,
    result_snapshot JSON NOT NULL,
    result_snapshot_hash CHAR(64) NOT NULL,
    data_snapshot_version VARCHAR(80) NOT NULL,
    contract_version VARCHAR(80) NOT NULL,
    constraint_version VARCHAR(80) NOT NULL,
    parameter_version VARCHAR(80) NOT NULL,
    input_count INT UNSIGNED NOT NULL,
    scheduled_count INT UNSIGNED NOT NULL,
    unplaced_count INT UNSIGNED NOT NULL,
    data_rejected_count INT UNSIGNED NOT NULL,
    hard_constraint_violations INT UNSIGNED NOT NULL,
    created_at DATETIME(6) NOT NULL,
    CONSTRAINT fk_revision_trip FOREIGN KEY (trip_id) REFERENCES trips(trip_id),
    CONSTRAINT fk_revision_intent FOREIGN KEY (generation_intent_id)
        REFERENCES generation_intents(generation_intent_id),
    CONSTRAINT fk_revision_solver_run FOREIGN KEY (solve_run_id)
        REFERENCES solver_runs(solve_run_id),
    CONSTRAINT uq_trip_revision_no UNIQUE (trip_id, revision_no),
    CONSTRAINT uq_revision_intent UNIQUE (generation_intent_id),
    CONSTRAINT uq_revision_solver_run UNIQUE (solve_run_id),
    CONSTRAINT ck_revision_accounting CHECK (
        input_count = scheduled_count + unplaced_count + data_rejected_count
    ),
    CONSTRAINT ck_revision_hard_gate CHECK (hard_constraint_violations = 0)
);

CREATE INDEX ix_trip_revisions_trip_created
ON trip_revisions(trip_id, created_at);
```

Revision 只保存质量门通过的 complete 或 partial 结果；软降级通过独立布尔值和 `result_snapshot.degradations` 表达，因此可与 partial 同时存在。无解、整体数据失败和内部错误不创建空 Revision。`result_snapshot` 中的 node ID 在首次映射时生成并永久保存，不能每次 GET 动态生成。

### 8.5 完成事务

```text
1. 重新读取 intent，确认仍为 running
2. 插入 solver_runs
3. 如成功，创建或读取 Trip
4. 分配 revision_no 并插入 trip_revisions
5. 更新 trips.current_revision_id
6. 更新 intent.trip_id/revision_id/status/completed_at
7. commit
```

求解器执行在事务外；完成保存使用短事务。唯一约束是最终并发保护。事务失败不能留下半个 Revision，也不能让 intent 显示 completed。

当前物理迁移 `0003_trip_revision_lineage` 已为 `generation_intents` 增加 `target_trip_id/base_revision_id`，并落实 `(trip_id, revision_number)` 唯一约束。该迁移不重写任何历史 Revision；现有首次生成 Intent 的两个新字段保持 `NULL`。

## 9. 反馈和计划分享（M1 P1）

```sql
CREATE TABLE feedbacks (
    feedback_id VARCHAR(64) PRIMARY KEY,
    feedback_intent_id VARCHAR(64) NOT NULL,
    principal_id VARCHAR(64) NOT NULL,
    trip_id VARCHAR(64) NOT NULL,
    revision_id VARCHAR(64) NOT NULL,
    feedback_scope VARCHAR(20) NOT NULL,          -- trip | node
    target_key VARCHAR(96) NOT NULL,              -- trip | node:<node_id>
    node_id VARCHAR(64) NULL,
    rating VARCHAR(20) NOT NULL,
    reason_codes JSON NOT NULL,
    comment VARCHAR(500) NULL,
    created_at VARCHAR(40) NOT NULL,
    updated_at VARCHAR(40) NOT NULL,
    CONSTRAINT uq_feedbacks_intent UNIQUE (feedback_intent_id),
    CONSTRAINT uq_feedbacks_principal_revision_target
        UNIQUE (principal_id, revision_id, target_key)
);

CREATE TABLE plan_shares (
    plan_share_id VARCHAR(64) PRIMARY KEY,
    plan_share_intent_id VARCHAR(64) NOT NULL,
    principal_id VARCHAR(64) NOT NULL,
    trip_id VARCHAR(64) NOT NULL,
    revision_id VARCHAR(64) NOT NULL,
    status VARCHAR(20) NOT NULL,
    template VARCHAR(20) NOT NULL,
    public_token_hash VARCHAR(64) NOT NULL,
    share_schema_version VARCHAR(32) NOT NULL,
    share_snapshot JSON NOT NULL,
    share_snapshot_hash VARCHAR(64) NOT NULL,
    created_at VARCHAR(40) NOT NULL,
    published_at VARCHAR(40) NOT NULL,
    revoked_at VARCHAR(40) NULL,
    CONSTRAINT uq_plan_share_intent UNIQUE (plan_share_intent_id),
    CONSTRAINT uq_plan_share_public_token_hash UNIQUE (public_token_hash)
);
```

`plan_shares` 在创建事务中校验主体拥有 Trip、Revision 属于该 Trip，并保存创建时生成的 `plan-share-v1` 脱敏快照；公开读取不再动态联表重算。`public_token_hash` 是公开 token 的 SHA-256 摘要，数据库不保存 token 原值；`share_snapshot_hash` 用于检测快照意外变化。当前首版只创建 `published/simple` 对象；`revoked_at` 为后续撤回能力保留，尚未提供作者撤回 API/UI。图片对象键不进入 0004，PNG/JPEG 导出、二维码和原生平台分享属于 A6-9.3.1。

`feedbacks` 保存规范化后的首份反馈。`feedback_intent_id` 负责同一网络意图的幂等与冲突检测；`(principal_id, revision_id, target_key)` 保证同一主体对同一 Revision 整体或节点目标只存在一份样本。`target_key` 的整体值为 `trip`，节点值为 `node:<node_id>`。节点提交前必须验证 node ID 存在于对应 Revision 的不可变结果快照；越权、Revision 不属于 Trip、node 不属于 Revision 均在应用层统一为 404。当前首版没有 UPDATE/编辑反馈流程，重复目标只返回首份记录。

反馈评价行程安排质量，不等于景点评分。计划分享与 M2 TripRetrospective 不复用表、快照 Schema、token 密钥或权限语义。

## 10. JSON Snapshot Schema

### 10.1 规范化输入

必须包括：

```text
schema_version
city_id/timezone
start_date/end_date
arrival transport/value/confirmation/reserve/source
departure transport/value/confirmation/reserve/source
travel_mode/crowd_type
selected attraction IDs（稳定排序）
user visit-period preferences（稳定排序）
data_snapshot_version
```

对象键和集合按固定规则规范化；不包含 request ID、保存时间等噪声。哈希算法和 canonicalization 版本进入 `input_schema_version`。

### 10.2 结果快照

必须包括：

```text
summary
provenance
accounting
days.timeline（稳定 node ID）
unplaced
data_rejected
degradations
```

结果哈希排除 elapsed_ms 等非确定字段。历史 revision 按自身 Schema 版本读取；迁移不得覆盖历史 snapshot 原文。

## 11. 保留、删除和不可变性

| 数据 | 默认保留 | 删除/匿名化 |
|---|---|---|
| 当前月运行日志 | 当前月 | 按日志策略，不记录 token/直接身份 |
| 压缩日志 | 180 天 | 按保留期清理 |
| 匿名草稿 | 产品配置保留期 | 删除或匿名化主体关联 |
| Trip/Revision | 账号/匿名策略 | 用户不可见并按策略清理；审计关联匿名化 |
| SolverRun | 至少 M1 验证周期，默认 180 天 | 通过 intent 匿名化主体，不改写约束证据 |
| 景点 revision | 长期 | 不随用户删除 |

正常业务操作不能 UPDATE 改写历史 Revision/SolverRun；删除通过可见性和受控清理实现。

## 12. 事务与失败恢复

| 用例 | 事务 |
|---|---|
| 创建/更新草稿 | 单短事务，version 条件更新 |
| 提交 intent | 单短事务保存不可变输入和 queued 状态 |
| 领取执行 | 单条件 UPDATE |
| 求解 | 无数据库事务 |
| 保存完成结果 | SolverRun + Trip + Revision + Intent 单短事务 |
| 提交反馈 | 归属/节点校验 + intent/目标去重 + Feedback 单短事务；数据库唯一约束处理并发终态 |
| 数据发布 | building 校验后原子切换城市当前快照指针 |

恢复任务扫描 running 且租约超时的 intent，根据执行器状态转 `failed_retryable`。重试不换输入、数据版本或 seed，并创建新 SolverRun `run_no`。

## 13. Alembic 迁移顺序

```text
0001_planning_core
  → M1 草稿、Trip、GenerationIntent、SolverRun、TripRevision 基线
0002_anonymous_identity
  → 匿名主体凭证
0003_trip_revision_lineage
  → target_trip_id/base_revision_id、Trip 内 Revision 唯一约束
0004_plan_shares
  → 公开 token 摘要、plan-share-v1 不可变脱敏快照和查询索引
0005_feedbacks
  → Revision/节点反馈、intent 幂等和主体/Revision/目标去重约束
0006_place_catalog
  → 通用 Place、来源、Revision、几何、访问点、时间、关系、互斥组和求解投影发布边界
0007_admin_identity_audit
  → 独立管理员身份、角色、会话摘要、服务端 RBAC 版本和追加式业务审计
```

以上是仓库当前实际物理迁移链，不再沿用早期把每一组概念表拆成 001–010 的预估编号。服务器真实 MySQL 当前仍停在 `0002_anonymous_identity`；R0.3 部署前必须先备份，再依次执行 0003、0004、0005、0006、0007、0008、0009、0010，并确认 readiness 的 `expected_revision/current_revision` 都是 `0010_place_revision_version`。R0.2-05-02 只在临时 SQLite 测试库从空库执行完整 `upgrade head`，未连接或变更服务器数据库。

每次迁移必须：

- 有 downgrade 或明确不可逆理由；
- 不在 DDL 中请求网络数据；
- 种子数据与 Schema 迁移分离；
- 在测试数据库从空库完整升级；
- 验证 FK、唯一约束和 CHECK；
- 生产迁移前备份并记录版本。

## 14. 数据模型验收场景

### A5-DATA-01 草稿乐观锁

```gherkin
Given draft_version=4
When 两个事务都以 expected_version=4 更新
Then 只有一个 UPDATE 成功
And 另一个返回 version conflict
And 最终版本为 5
```

### A5-DATA-02 intent 幂等与原子领取

```gherkin
Given generation_intent_id=G 已存在且 status=queued
When 重复插入 G 并有两个 executor 同时领取
Then 主键阻止第二条 intent
And 应用比较 input_snapshot_hash
And 只有一个 executor 将状态更新为 running
```

### A5-DATA-03 完成事务原子性

```gherkin
Given 求解质量门通过
When 保存 Revision 的事务失败
Then 不存在半完成 Revision
And current_revision_id 不指向不存在记录
And intent 不显示 completed
```

### A5-DATA-04 历史不可变

```gherkin
Given Trip 已有 revision 1
When 用户修改草稿并重新生成
Then 创建 revision 2
And revision 1 的输入和结果哈希不变
And current_revision_id 指向 revision 2
```

### A5-DATA-05 守恒和硬门

```gherkin
Given input=7 scheduled=5 unplaced=1 rejected=0 或 hard violations>0
When 保存成功 Revision
Then CHECK/应用门禁拒绝该记录
And 不产生可展示成功结果
```

### A5-DATA-06 发布快照

```gherkin
Given building snapshot 的 OD 存在缺失边
When 发布门运行
Then 不切换城市当前快照指针
And validation_report 保留缺失边
And 非同点 travel_min=0 被拒绝
```

### A5-DATA-07 地点投影发布边界

```gherkin
Given PlaceRevision 为 human_verified
And 到达/离开访问点、几何和时间规则均 human_verified
And 来源闭包、重叠裁决和 projection hash 完整
When 仓储执行 publish_projection
Then Revision 与 SolverPlaceProjection 在同一事务中进入 published
And 直接插入 published 对象被拒绝
```

### A5-DATA-08 不完整地点稳定拒绝

```gherkin
Given 访问点未审核、时间规则缺失、同日表演场次歧义或重叠关系未裁决
When 运行 projection publication gate
Then 返回稳定 reason codes
And 不修改 candidate/human_verified 状态
And 不生成 published research snapshot
```

## 15. A5 数据退出条件

- [x] 主体、草稿、Intent、SolverRun、Trip 和 Revision 关系明确；
- [x] 草稿乐观锁、intent 幂等、执行原子领取和 Revision 唯一约束明确；
- [x] 求解完成事务和失败恢复明确；
- [x] 输入/结果 snapshot、哈希和 Schema 演进明确；
- [x] 多时间规则、多闭馆日、日期例外结构化；
- [x] 天气、有向 OD、时段偏好和发布快照可追溯；
- [x] SolverRun 满足 ADR-0005 审计字段；
- [x] Revision 只保存质量门通过且守恒的结果；
- [x] token、日志、删除和保留边界明确；
- [x] 迁移顺序和数据库验收场景明确；
- [x] 通用地点、来源、Revision、几何、访问点、时间、关系、互斥组和单节点投影已形成 0006 物理模型；
- [x] candidate/human_verified/published 状态隔离和稳定 projection hash 发布门禁已实现；
- [x] 未提前创建 Execution/Journal/Community/Retrospective 空表。

## 16. OM1 管理端数据模型（身份与审计底座已实现）

本节定义 R0.2-05 的分阶段模型。`0007_admin_identity_audit` 已追加实现 16.1 和 16.4；`0008_place_review_workflow` 已追加实现 16.2 审核任务与决定；`0009_place_revision_review_flags` 已追加实现候选 Revision 数据质量/审核标记；`0010_place_revision_version` 已追加 Revision 子资源写入所需的乐观锁版本。O04 与 O05 的写入/逐项审核复用现有 0006 事实表和 0010 Revision 乐观锁，不新增空壳迁移；16.3 发布批次仍待 R0.2-07 通过新迁移追加。0001–0009 未被改写。

### 16.1 管理身份

#### `admin_actors`

| 字段 | 说明 |
|---|---|
| `admin_actor_id` | 稳定内部 ID |
| `login_name` | 唯一登录名或外部身份映射键；不与普通 principal 混用 |
| `credential_digest` | 使用选定认证方案的安全摘要；SSO 时可为空 |
| `status` | active/disabled/locked |
| `version` | 管理员资料/角色乐观锁版本 |
| `session_version` | 角色或安全状态变化时使旧会话失效 |
| `created_at/updated_at` | 审计时间 |

#### `admin_roles` / `admin_actor_roles`

- 角色键至少包括 `data_editor/data_reviewer/data_publisher/research_viewer/content_moderator/admin_security`；
- `(admin_actor_id, role_key)` 唯一；
- 角色分配和撤销不物理删除审计事实；
- 最后一个 `admin_security` 的移除必须有恢复策略和高风险门禁。

#### `admin_sessions`

- 只保存不可逆 session/token 摘要；
- 保存 actor、session_version、expires_at、revoked_at 和必要安全元数据；
- 保存签发时 `issued_role_keys`；认证时必须与 actor 当前 role set 和 session_version 同时一致；
- 不保存密码、token 原值或完整 User-Agent；
- 普通用户匿名凭证不能作为 admin session 外键或自动升级来源。

### 16.2 审核任务与决定

#### `place_review_tasks`

| 字段 | 说明 |
|---|---|
| `review_task_id` | 主键 |
| `place_revision_id` | 准确待审 Revision；同一开放任务唯一 |
| `status` | draft/ready_for_review/in_review/changes_requested/approved/closed |
| `assigned_reviewer_id` | 可空；绑定 AdminActor |
| `version` | 乐观锁 |
| `created_by/created_at/updated_at` | 创建和时间事实 |

ReviewTask 状态不能替代 `PlaceRevision.review_status`；它表达人员工作流，Revision 表达业务事实成熟度。

#### `place_review_decisions`

- 追加式记录 approve/request_changes/cancel 等决定；
- 绑定 task、Revision、actor、actor role、reason code、受限说明和 created_at；
- approve 与 Revision 进入 human_verified 在同一事务中完成；
- 不允许 UPDATE 改写历史决定，纠正通过新决定或新任务表达。

### 16.3 发布批次

#### `place_publication_batches`

- 保存 publication_intent_id、发起人、状态、目标数据版本、规范化输入哈希、质量报告摘要和时间；
- 同 publication_intent_id 只对应一个规范化载荷；
- 批次状态建议 `previewed/running/completed/partial_failed/failed`；
- 批次成功不替代逐 Revision/Projection 的 published 状态。

#### `place_publication_batch_items`

- 绑定 batch、place_revision、projection、结果和稳定 reason codes；
- `(batch_id, place_revision_id)` 唯一；
- 部分失败必须可逐项查询，不能只保留一个批次错误字符串。

研究快照继续使用现有发布快照边界；如当前物理表不足，后续迁移只追加快照与批次关系，不改写历史 snapshot 内容。

### 16.4 管理业务审计

#### `admin_audit_events`

| 字段 | 说明 |
|---|---|
| `audit_event_id` | 追加式主键 |
| `actor_id/actor_role` | 操作者及当时生效角色 |
| `action` | 稳定动作码 |
| `target_type/target_id/target_revision` | 被操作对象 |
| `before_digest/after_digest` | 规范化前后摘要，不保存完整秘密/第三方正文 |
| `reason_code/reason_text` | 结构化理由；自由文本受限 |
| `request_id/operation_intent_id` | HTTP 和幂等关联 |
| `operation_digest` | 规范化非敏感操作载荷摘要，用于识别同 intent 不同载荷 |
| `result/error_code` | succeeded/rejected/failed 及稳定码 |
| `occurred_at` | UTC 时间点 |

审计表与 ADR-0005 文件日志分离：

- 日志每日分级并按月压缩，可按保留期清理；
- 管理审计默认长期保留，按合规策略归档；
- 日志异常不能导致业务事务伪成功；审计写入与高风险业务状态变更应在同一事务或可靠 outbox 中完成；
- 管理端只读查询，不能提供编辑/删除 API。

### 16.5 OM1 数据验收场景

```gherkin
Given data_editor 创建并送审 candidate Revision
When reviewer approve
Then ReviewDecision、Revision=human_verified 和 AuditEvent 原子提交
And editor 不能伪造 reviewer actor

Given published Revision 需要修改
When editor 保存新事实
Then 创建新的 candidate Revision
And 原 published Revision、Projection、TripRevision 和研究快照哈希不变

Given 月度运行日志已经压缩并清理
When 查询同月的地点发布操作
Then admin_audit_events 仍可按 actor、target 和 publication intent 查询
```

### 16.6 OM1 中国法定节假日历自动同步（计划，G7-R0.2-09）

本节是 ADR-0021 已接受的计划模型，当前代码内置 2025/2026 年日历不等于以下持久化模型已实现。迁移必须使用新的 Alembic revision 追加，不能改写既有迁移或历史 `PlaceDateException`。

#### `holiday_calendars`

| 字段 | 说明 |
|---|---|
| `holiday_calendar_id` | 年度日历不可变版本 ID |
| `region_code/calendar_year/version` | 首版固定中国大陆 `CN`；同地区、年份、版本唯一 |
| `status` | draft/published/superseded；只有 published 可供 O05 使用 |
| `display_name` | 面向管理端的中文年度名称 |
| `source_record_id` | 关联官方公告来源记录，不保存网页凭证 |
| `source_content_sha256` | 原始 HTML/PDF/附件内容哈希 |
| `normalized_digest` | 规范化假期与调休载荷摘要，用于幂等和差异判断 |
| `supersedes_calendar_id` | 官方修订时指向被替代版本 |
| `published_at/created_at/updated_at` | 生命周期与审计时间 |

已发布行不可原地修改；官方内容变化必须创建 v2 等新版本，并将旧版本标记为 superseded。相同官方内容重复同步不得创建重复版本。

#### `holiday_periods`

- 保存 `holiday_period_id/holiday_calendar_id/holiday_name/start_date/end_date/display_order`；
- 每段保存可定位到官方原文的 `evidence_quote` 或等价受控证据定位；
- 日期范围必须通过年份、顺序、重叠、完整性和规范化校验。

#### `holiday_adjusted_workdays`

- 保存 `adjusted_workday_id/holiday_calendar_id/service_date/holiday_name/evidence_quote`；
- 调休工作日用于忠实保存公告和冲突校验；M1 不据此自动改变地点开放状态。

#### `holiday_calendar_sync_jobs`

| 字段组 | 说明 |
|---|---|
| 身份与输入 | `sync_job_id/region_code/year/mode` |
| 生命周期 | queued/running/not_announced/temporarily_unavailable/needs_attention/published/up_to_date/failed |
| 官方来源 | `source_url/source_title/source_published_at/source_content_sha256` |
| 处理结果 | `validation_result/calendar_id/attempt_count/next_retry_at` |
| 幂等与审计 | `operation_intent_id/operation_digest/created_by/created_at/started_at/finished_at` |

同步按钮、周期任务和 AI Tool 共用同一 Job 与应用服务。AI/定时任务使用受限系统主体，`created_by` 不得伪装成人工管理员；同一 operation intent 的不同载荷必须拒绝，相同年度同一时刻只允许一个运行任务。

SourceRecord 或等价来源快照必须保存官方 URL、观察时间、内容哈希和允许的证据摘要。业务审计保存动作、结果码、Job、版本和摘要，不保存模型密钥、网页凭证或无必要的完整网页正文。

新日历版本只影响后续 O05 生成。已经物化、审核或发布的 `PlaceDateException`、Projection、TripRevision 和研究快照不回写；影响查询只产生待办或候选修订建议。

### 16.7 OM1 地点数据采集（计划，O18 / G7-R0.2-05-03）

本节是 O18 的持久化边界，当前尚未创建对应迁移。实现时必须追加新的 Alembic revision，不能把采集表塞入既有地点事实表，也不能把采集结果直接写入 `human_verified` 或 `published`。采集数据的唯一合法路径为：

```text
CollectionBatch/Attempt/Result
  → staging 结果与差异
  → candidate PlaceRevision + SourceRecord + RelationClue
  → O04/O05/O06/O07 人工审核
  → Projection / Publication Gate
```

#### `collection_batches`

| 字段组 | 字段 | 说明 |
|---|---|---|
| 身份 | `collection_batch_id` | 不透明、稳定的批次 ID |
| 范围 | `region_code/city_code/area_ids/target_fields` | 结构化采集范围；不得使用自由 SQL |
| 来源 | `source_registry_id/source_registry_digest/field_dictionary_digest` | 固化本批次使用的来源和字段白名单版本 |
| 执行 | `status/collector_version/parser_version` | 状态见 O18；版本用于回放 |
| 统计 | `requested/succeeded/failed/rate_limited/excluded` | 批次级守恒计数 |
| 幂等 | `operation_intent_id/operation_digest` | 同 intent 同载荷可重放，不同载荷拒绝 |
| 审计 | `created_by/created_at/started_at/finished_at` | 人工、系统或 AI Tool 主体必须可区分 |

批次完成只表示执行结束，不代表任何事实已核验。`status=partially_failed` 必须能分别查询成功、失败和排除清单。

#### `collection_attempts`

每个外部请求或页面处理尝试保存：`attempt_id/batch_id/source_id/request_fingerprint/started_at/finished_at/result_code/retry_count/next_retry_at`。不得保存 API Key、Cookie、Authorization、完整响应正文或未授权媒体；请求指纹必须脱敏并可用于去重和审计。

#### `collection_results`

| 字段 | 说明 |
|---|---|
| `collection_result_id/batch_id` | 结果及所属批次 |
| `source_record_draft` | 允许字段的来源摘要、URL、观察时间和内容哈希；仅作为 staging 草稿 |
| `normalized_payload` | 归一化后的候选字段，不包含发布状态 |
| `entity_match_status` | `new_entity/same_entity/possible_duplicate/distinct_entity` |
| `result_status` | `candidate/needs_review/failed/excluded` |
| `field_conflicts` | 字段级来源差异及证据定位 |
| `relation_clues` | 可回放的关系候选，不是已成立关系 |
| `evidence_locator` | 官方页面/公告中的受控定位信息 |
| `input_hash/output_hash` | 用于幂等和回放，禁止用来代替人工核验 |

同一结果重复物化时，按 `(batch_id, input_hash, normalized_payload)` 幂等；任何字段变化都必须创建新的 candidate Revision 或新的采集结果版本，不能原地覆盖已发布数据。

#### `relation_clues`

关系线索至少保存：`clue_id/left_place_ref/right_place_ref/relation_candidate/reason_code/evidence_source_record_id/detector_version/confidence/review_status/created_at`。端点可以先引用候选实体，只有两端 Place 均可解析时才能延迟导入 `place_relations`；`review_status=unresolved` 不得进入求解投影。O07 负责裁决和“确认无关系”，不提供无证据的任意关系新增入口。

#### 保留与删除

批次运行摘要、差异、失败原因、输入/输出哈希和审计引用按治理保留；原始响应只在来源条款允许且有明确 TTL 时短期缓存。凭证、令牌、完整页面正文和未授权媒体不得进入上述任何表。运行日志与业务审计继续按 ADR-0005 分离，日志归档不能删除批次和审核审计事实。

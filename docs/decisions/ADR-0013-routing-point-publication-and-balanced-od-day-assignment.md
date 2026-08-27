# ADR-0013：路线点发布门禁与 OD 分天负载均衡

- 状态：Accepted
- 日期：2026-08-26
- 产品里程碑：M1
- 实现优先级：P0
- 关联：ADR-0004、ADR-0009、ADR-0010、ADR-0011、ADR-0012、H3、C1、C2、C4、C5、C6

## 背景

ADR-0012 已把默认分天升级为 OD 感知聚类，并在首份 42/42 高德严格快照上消除了明显跨区往返。但进一步使用高德 POI 服务核对景点位置、按候选游客点位重建完整 OD 后，暴露出两个仍会影响真实发布质量的问题：

1. 裸 `lat/lng` 无法说明坐标代表景区入口、售票处、表演地点还是开放街区代表点。浙江省博物馆、西湖湖滨和音乐喷泉原 fixture 与高德候选点分别偏移约 636m、652m 和 755m；大型景区、多门场馆和开放街区不能仅凭名称搜索第一条结果自动发布。
2. average-linkage 聚类只限制单簇最大数量 `ceil(N / D)`，仍可能在七景点三日场景形成 `3/3/1`。只修数量后又可能形成建议游览负载 `420/210/170min`，导致一天过满、一天明显空闲。

这两类问题不改变 C1/C2/C4/C5/C6 硬约束定义或 `trip-result-v2` 字段结构，但会改变已发布数据门禁、稳定主方案的分天软目标和默认数值参数，因此必须版本化。

## 决策

### D1 路线点必须携带来源与点位语义

进入正式 published 快照的每个景点路线点至少保存：

```text
gaode_poi_id
routing_point_kind
coordinate_source
coordinate_fetched_at
coordinate_review_status
lat / lng
```

其中：

- `gaode_poi_id` 用于稳定追溯高德对象，不能只保存当时返回的经纬度；
- `routing_point_kind` 必须说明游客到达语义，例如 `visitor_entrance`、`ticket_office`、`performance_location` 或 `area_representative`；
- `coordinate_source` 和 `coordinate_fetched_at` 记录来源与抓取批次；
- `coordinate_review_status=human_verified` 才能进入 `status=published` 的正式快照；
- 候选快照必须显式标记 `status=candidate`，且只有审计工具显式启用 candidate 模式时才能加载。

大型或多门景区需人工确认实际游客动线；开放街区没有唯一入口时，必须明确代表点口径；固定表演地点不能复用泛化街区坐标。自动 POI 命中和 API 成功不等于已完成人工校准。

### D2 发布快照是不可变、可校验的离线求解输入

`published-solver-data-v1` JSON Provider 作为正式数据库接入前的可执行发布适配器，必须：

- 校验 SHA-256 内容哈希；
- 校验快照版本、景点 ID、外部 ID、天气日期唯一；
- 校验完整 `N×(N−1)` 有向 OD，禁止 missing、重复或静默补零；
- 校验所有 OD 的 basis 和 data version 与快照声明一致；
- 默认拒绝 candidate，正式 published 强制所有路线点 `human_verified`；
- 加载后只构造内存 Provider，求解过程不调用高德 HTTP。

正式 MySQL PublishedDataProvider 后续必须保持相同的发布与回放语义。历史快照和历史 TripRevision 不覆盖、不迁移、不原地重算。

### D3 OD 聚类后先做数量均衡

初始 average-linkage 聚类完成后，在不改变景点集合的前提下移动 OD 代价增加最小的景点，使所有日期的景点数量差不超过 1：

```text
max(day_count) - min(day_count) <= 1
```

移动成本使用双向对称 OD，不把缺边视为 0；相同成本按景点 ID、簇成员和目标簇稳定打破平局，保证可回放确定性。

### D4 在数量平衡内继续优化建议游览时长

数量满足 floor/ceil 平衡后，允许继续移动景点以减少每日建议游览总时长的极差，但必须同时满足：

- 移动后各日数量仍在 `floor(N/D)` 与 `ceil(N/D)` 范围内；
- 建议游览时长极差严格减小；
- 景点加入目标簇相对留在原簇的双向对称 OD 平均代价增量不超过 `10min`；
- 不为压平时长拆散湖滨/音乐喷泉、灵隐寺/飞来峰等强近邻组合；
- 该步骤只生成默认日期偏好，最终日期仍由可用性、容量、锚点、天气和跨天重分配决定。

`10min` 是当前真实杭州样本与反例测试共同确定的保守阈值，属于机器参数而非永久常量。

### D5 版本组合

本次不改变请求结构或公开结果字段，版本组合升级为：

```text
solver contract    = solver-p1-v2
result schema      = trip-result-v2
constraint version = constraints-p1-v4
parameter version  = parameters-p1-2026-08-26
```

机器契约新增：

```text
soft objective = OD_DAY_ASSIGNMENT
od_duration_rebalance_max_symmetric_penalty_min = 10
```

保留 `solver-p1-v1`、`constraints-p1-v1/v2/v3`、`parameters-p1-*` 和 `DEFAULT_SOLVER_P1_CONTRACT` 等历史机器标识。历史 Revision 继续按生成时的版本回放。

## 真实验证证据

使用高德 Web 服务 V3 检索并生成 7 个候选路线点；有效节流请求均返回 `status=1 / infocode=10000`。候选点重建的严格 OD：

```text
requested_pair_count = 42
gaode_pair_count     = 42
fallback_pair_count  = 0
missing_pair_count   = 0
mode_failures        = 4（均为 transit no_route，其他模式成功）
duration             = 5–61min
distance             = 324–11,587m
```

初始真实结果与两次修复：

```text
初始聚类数量：       3 / 3 / 1
数量均衡后负载：   420 / 210 / 170min
最终数量：           2 / 3 / 2
最终建议时长负载： 300 / 290 / 210min
最终交通：          80min / 7,135m
```

最终稳定分天：

```text
Day 1：飞来峰 → 灵隐寺
Day 2：浙江省博物馆 → 西湖湖滨 → 湖滨晚间表演
Day 3：雷峰塔 → 河坊街
```

结果为 7/7 景点守恒、0 未排入、4/4 实际连接来自高德、硬质量门禁通过；结果哈希为：

```text
98705e1a8e3a92c62eb415126015faa367efa997b589b40ce26af2c4cff2b687
```

该证据证明候选点位和当前算法可形成稳定可行结果，不代表候选坐标已完成人工发布审核，也不等同于 H3 已通过专家或用户验证。

## 影响与代价

- 正式发布多一个人工路线点审核步骤，但避免把错误入口造成的虚假近邻或虚假远距写入长期快照；
- 分天比单纯聚类多两个确定性修正阶段，七景点与当前目标规模的计算开销可忽略；
- 数量差不超过 1 是默认体验目标，不承诺所有日期最终都同样饱满；闭馆、天气、锚点和容量等硬条件可导致最终不均衡；
- 建议时长均衡允许最多 10 分钟的局部 OD 代价增加，换取更可用的日负载，但不会接受明显跨区移动；
- 当前候选天气是明确标注的审计 normal fixture，不得描述为实时天气或生产发布数据。

## 验收

- 未经 `human_verified` 的坐标不能作为 published 快照加载；
- candidate 只有显式审计开关才能加载；
- 哈希篡改、坐标来源缺失、OD 不完整、basis 或版本混用均加载失败；
- 七景点三日反例稳定由 `3/3/1` 修正为数量差不超过 1；
- 建议时长修正只在 OD 增量不超过 10 分钟时发生，强近邻不被拆散；
- 真实候选快照离线回放稳定得到 `2/3/2`、80min、7,135m 和相同结果哈希；
- 全量测试、Golden、降级、接近度、数据校验、性能和前端门禁通过。

## 何时重新评审

- 正式人工入口审核显示当前候选点位或 `routing_point_kind` 不足以表达游客动线；
- M2 引入酒店、餐厅、锁定节点或 arrival/departure 双路线点，需要跨节点类型联合优化；
- 真实城市规模下数量均衡或 10 分钟阈值持续产生不合理路线；
- 专家/用户证据支持按有效游玩时间、营业窗口或区域容量替代当前建议时长负载；
- MySQL 发布流程、跨机器缓存或多地图 Provider 需要升级快照 schema。

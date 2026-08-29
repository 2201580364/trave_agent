# ADR-0018：通用地点目录、访问点与求解投影

- **状态**：已接受
- **日期**：2026-08-29
- **决策者**：产品 + 工程
- **产品里程碑**：M1 — 行程骨架验证
- **实现优先级**：P0
- **关联假设**：H3、H6、H7
- **前置**：ADR-0002、ADR-0009、ADR-0011、ADR-0013、ADR-0016、ADR-0017

## 背景与问题

Gate 6 和 A6 使用 7 个点状杭州路线点完成了求解器、真实高德 OD、天气、持久化和浏览器纵向切片，但 Gate 7 形成性测试还需要 40–60 个点状地点及 10–15 个街区、景区、路线、市集、表演等非普通点实体。

现有 `attractions`、`Attraction` 和 `published-solver-data-v1` 默认一个可选对象只有一个坐标，无法可靠表达：

- 多入口景区的游客到达点与离开点；
- 街区、夜市和开放区域的边界、代表入口与非全天营业商户；
- 步行路线的起点、终点、内部步行和单向游览语义；
- 固定表演的实际演出地点与场次时间；
- 同一景区总入口与内部子景点重叠选择造成的重复排程；
- 来源记录、事实修订与历史求解输入之间的可追溯关系。

直接把区域中心点写成“景点坐标”，或把路线拆成多个用户未选择的普通景点，会产生伪精确 OD、景点守恒破坏、游览时长重复计算和历史结果无法解释等问题。另一方面，M1 当前求解器契约已经稳定，现阶段全面改写为通用多几何、多节点求解器会扩大 Gate 7 前置范围并增加回归风险。

## 决策

### D1 通用 `Place` 是事实源，`Attraction` 只保留为求解模型

建立与求解器解耦的通用地点目录。逻辑实体至少包括：

```text
places
├── place_access_points
├── place_geometries
├── place_source_records
├── place_revisions
├── place_time_rules / closures / exceptions
├── place_relations / selection exclusion groups
└── solver_place_projections
```

`Place` 保存用户认识的旅行对象和经审核的业务事实；当前 `travel_agent.solver.Attraction` 继续只是 M1 求解器需要的最小不可变节点。数据发布过程通过版本化投影把 `PlaceRevision` 转换为 `Attraction`，求解器不得反向成为地点事实的权威来源。

`place_id` 使用稳定、不透明的字符串业务 ID，不把名称、类型、经纬度或第三方 POI ID 编码进主键。名称、类型、入口和来源发生变化时创建新 revision，不更换 `place_id`；合并重复实体时保留 alias/redirect 和裁决记录，不能静默删除历史引用。

### D2 首批地点类型与几何类型使用封闭枚举

M1/G7-R0.2 接受以下 `place_kind`：

```text
attraction
scenic_area
neighborhood
walking_route
market
show
experience
```

接受以下 `geometry_kind`：

```text
point
area
route
```

含义如下：

| `place_kind` | 典型对象 | 主要发布要求 |
|---|---|---|
| `attraction` | 博物馆、寺庙、塔、单体场馆 | 审核游客入口；开放、闭馆、最晚入园可解析 |
| `scenic_area` | 大型景区、公园、复合景点 | 不使用几何中心；明确默认到达/离开点和内部游览预算 |
| `neighborhood` | 湖滨、历史街区、网红区域 | 明确代表入口口径；开放公共空间与商户营业时间分开 |
| `walking_route` | 运河漫步、九溪路线 | 审核起点和终点；路线内部步行计入游览时长，不计入节点间 OD |
| `market` | 夜市、市集、周期集市 | 保存真实营业/举办时段和日期例外；不能因所在街区开放而标为全天营业 |
| `show` | 灯光秀、演出、固定场次 | 使用实际演出地点；当前投影只接受每个研究日期唯一、无歧义的目标场次 |
| `experience` | 茶园体验、手作、预约活动 | 明确预约/入场窗口、时长和实际集合点 |

类型是发布语义，不是展示标签。未知类型不得自动退回 `attraction`；新增枚举必须评审数据门禁、UI 文案和投影规则。

### D3 几何与访问点分离，路线计算使用有方向的端点

几何用于表达范围和展示，访问点用于路线计算。`place_access_points` 至少保存：

```text
access_point_id
place_id / place_revision_id
access_point_kind
lat / lng
source_record_id
review_status
fetched_at / reviewed_at
active
```

首批 `access_point_kind`：

```text
visitor_entrance
visitor_exit
route_start
route_end
performance_location
meeting_point
area_representative
```

每个可发布的求解投影必须明确：

```text
arrival_access_point_id
departure_access_point_id
```

点状地点通常可让两者相同；路线通常分别使用 `route_start` 与 `route_end`；区域或景区可以使用同一默认入口，也可以使用经审核的默认入口/出口组合。

节点 A 到节点 B 的真实有向 OD 端点固定为：

```text
A.departure_access_point → B.arrival_access_point
```

OD 子图的身份和哈希必须包含两端 access point ID、对应 revision、地图 Provider、策略、模式和抓取时间。几何中心、未经审核的自动 POI 首条结果或缺失端点不得作为 published 路线点。

### D4 M1 每个用户可选地点只投影为一个求解节点

为了保持当前景点守恒、选择/替换、反馈、分享和 Revision 契约，M1 中一个可选 `PlaceRevision` 最多生成一个 `SolverPlaceProjection`，一个投影恰好对应一个当前 solver `Attraction`。

投影至少保存或固化：

```text
projection_id
projection_version
data_snapshot_version
place_id / place_revision_id
solver_node_id
place_kind / geometry_kind
arrival_access_point_id / departure_access_point_id
suggested_duration_min / recommended / max
internal_travel_min
Attraction 所需的时间、室内外、体力、状态和质量字段
projection_hash
```

规则：

- `solver_node_id` 是快照内整数 ID，只用于当前求解器和 OD 子图；必须与 `place_id` 的映射一同固化，不能由名称或数组顺序在运行时猜测；
- 现有 API 的 `attraction_id` 和 GenerationInput 字段名在 M1 暂不升级，但其值承载稳定 `place_id`；这是兼容别名，不表示事实模型仍只有普通景点；
- `Attraction.suggested_duration` 使用审核后的推荐值；最小值、最大值和来源保留在投影元数据，供宽松行程扩展、解释和后续版本使用；
- 路线、景区和区域内部的步行/游览预算计入节点游览时长，节点间 OD 只计算离开当前地点到抵达下一地点，禁止双重计时；
- `data_verified=true` 只能由完整投影门禁推导，不能直接复制单个来源的布尔值；
- 投影输入、规则版本和输出必须规范化计算 SHA-256，重复构建产生相同结果。

本决策不把求解器公共类立即重命名为 `PlaceNode`，也不修改 `solver-p1-v2`/`trip-result-v2`。只有公共字段或行为发生变化时，才按 ADR-0009/ADR-0011 升级契约版本。

### D5 区域、路线和表演使用受限但可执行的首版语义

为保证 R0.2 可落地，首版采用以下边界：

- `area`：保留面几何供审核和展示，求解只使用审核后的默认到达/离开点；不得向用户暗示系统优化了区域内部每一步；
- `route`：保留有序路线几何、起点和终点；首版只支持一个默认方向。反向路线必须是另一个明确投影或后续受控选项，不能在 OD 计算时临时交换端点；
- `show`：固定演出使用实际地点和可解析场次。当前 solver 无法表达同一地点同日多个可任选场次时，发布器必须为研究场景选择唯一目标场次，或将该地点标记为不可投影并给出原因；
- `always_open`：只描述公共空间本身，不继承内部场馆、商户、市集或演出的营业时间；
- 伪精确：UI 可以展示“约 1–2 小时”“傍晚场”等可理解范围，内部仍保存分钟级规则用于硬约束求解和回放。

### D6 重叠实体必须在进入求解器前裁决

地点目录允许保存 `contains`、`part_of`、`overlaps`、`same_experience` 等关系，但当前 solver 不承担通用图关系和互斥选择。

若一个聚合景区/路线与内部子地点代表同一段体验，发布时必须选择以下一种方式：

1. 只让其中一个实体具备 `solver_eligible=true`；
2. 为它们设置同一 `selection_exclusion_group`，在草稿确认和替换阶段拒绝同时选择；
3. 证明两者的时间、入口和体验范围不重叠，并留下人工裁决记录。

禁止把同一游览时间同时计入父地点和子地点，或依靠求解器事后“尽量分开”。

### D7 发布门禁按依赖闭包检查，失败必须显式

一个投影进入 immutable published research snapshot 前必须同时满足：

- Place、Revision 和 projection 均为 active，且业务必填字段完整；
- `place_kind` 与 `geometry_kind` 组合受支持；
- 到达/离开访问点均为 `human_verified`，来源和审核时间完整；
- 适用的开放时间、闭馆日、日期例外、最晚入园或固定场次可解析且冲突为 0；
- 推荐时长、室内外、体力和适用时段有来源或人工审核记录；
- 重复实体、重叠选择和来源硬事实冲突已裁决；
- projection 规范化构建稳定，ID 唯一，哈希正确；
- 实际求解使用的有向 OD 子图完整，缺边不填 0，近似不冒充高德；
- 历史快照、历史投影和 TripRevision 不被覆盖或原地重算。

未通过时输出稳定 reason code，例如：

```text
UNSUPPORTED_PLACE_KIND
MISSING_ARRIVAL_ACCESS_POINT
MISSING_DEPARTURE_ACCESS_POINT
ACCESS_POINT_NOT_HUMAN_VERIFIED
TIME_RULE_UNRESOLVED
FIXED_SESSION_AMBIGUOUS
OVERLAPPING_SELECTION_UNRESOLVED
SOURCE_CONFLICT_UNRESOLVED
PROJECTION_HASH_MISMATCH
```

采集成功、POI 命中或地点总数达标都不能绕过上述门禁。

### D8 版本、发布与兼容策略

R0.2 后续实现采用以下版本边界：

- 通用地点事实、来源记录和 revision 可更新，但 published snapshot 一经生成不可变；
- projection 规则使用独立 `projection_version`，规则变化必须生成新投影和新数据快照；
- `published-solver-data-v1` 和现有 7 点快照继续服务历史回放；新通用目录不得批量改写旧文件；
- R0.2-03 再确定具体 SQLAlchemy 表、约束和 Alembic revision，本 ADR 不预占迁移号；
- R0.2-06 再把当前完整 N² Provider 演进为按需 OD 子图，端点语义必须遵守本 ADR；
- 研究环境 manifest 绑定实际 published snapshot、projection version、projection hash 和 OD 子图身份。

## 备选方案与权衡

| 方案 | 优点 | 缺点 | 结论 |
|---|---|---|---|
| A. 继续扩展 `attractions` 并为所有对象保存一个坐标 | 改动最小 | 区域/路线语义失真，事实模型与求解器耦合，无法可靠表达进出点 | 不采纳 |
| B. 通用 `Place` + 访问点 + 版本化单节点求解投影 | 保持事实专业性和现有求解契约，能渐进迁移并回放 | 增加发布层和投影门禁；首版不支持复杂多节点地点 | **采纳** |
| C. 立即把求解器重写为通用多几何、多节点图 | 长期表达力最强 | 扩大 M1/Gate 7 范围，破坏已稳定契约和大量回归证据 | M2+ 有证据后重议 |
| D. 将路线/景区自动拆成多个隐藏景点 | 可复用当前节点算法 | 破坏用户选择守恒、替换和反馈语义，易重复计时 | 不采纳 |

## 后果

- **正面**：杭州研究目录可以专业表达点、面、路线、场次和访问点；OD 端点有明确游客语义；现有求解器与 API 可以稳定复用；历史快照继续可回放。
- **负面/代价**：需要新增来源、revision、访问点、关系和 projection 的数据模型与发布工具；每批数据需要人工审核访问点和硬事实；UI 需要识别地点类型与伪精确边界。
- **技术债务**：M1 仍使用 `Attraction`/`attraction_id` 命名承载通用地点投影；同日多场次、用户选择入口、路线双向、区域内部路径和一个地点多求解节点暂不支持。

## 验收

- 点状景点经投影后与现有 7 点 `Attraction` 行为等价；
- `walking_route` 使用不同的审核起点/终点，A→B OD 使用 A 的离开点和 B 的到达点；
- `area` 不允许用几何中心替代未审核入口；
- `market/show` 不继承所在公共街区的全天开放语义；
- 同日多场次无法唯一投影时稳定拒绝，不随机选择；
- 不完整或有冲突的地点不进入 published snapshot，并给出稳定 reason code；
- 重叠父子地点不能在无裁决时同时进入求解输入；
- 相同 revision、投影规则和端点产生相同 projection hash；
- 新快照不修改 `solver-p1-v2`/`trip-result-v2`，旧 `published-solver-data-v1` 仍可加载和回放；
- Gate 7 protocol canonical SHA-256 不因本数据模型决策而改变。

## 实施顺序

```text
R0.2-01 本 ADR
→ R0.2-02 source registry、合规登记与采集字段字典
→ R0.2-03 SQLAlchemy 数据模型、Alembic 迁移与 staging/published 边界
→ R0.2-04 杭州候选清单与覆盖矩阵
→ R0.2-05 采集、归一、去重、关系裁决和人工审核
→ R0.2-06 按需 OD 子图、缓存和回放
→ R0.2-07 数据门禁与 immutable research snapshot
```

## 何时推翻重议

- 专家验证表明一个 Place 必须拆成多个求解节点才能形成可执行路线；
- M2 餐厅、酒店、交通枢纽或行中当前位置需要进入统一节点图；
- 用户需要在生成时选择景区入口、路线方向或同日多个表演场次；
- 城市规模和多 Provider 数据要求专用地理数据库、拓扑网络或空间索引；
- `attraction_id` 兼容命名持续造成 API/UI 误解，需要升级为通用 `place_id` 契约；
- 投影层无法在不丢失关键事实的情况下继续适配当前 `Attraction`，届时必须升级 solver contract，而不是在 projection 中静默近似。

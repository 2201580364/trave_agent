# 旅行AI Agent — M1 MVP 技术选型文档

**版本**：V1.1  
**文档类型**：技术选型（已确认）  
**关联文档**：旅行助手产品文档.md（当前 V2.4）
**状态**：历史技术选型基线；具体应用架构、API、数据模型和首切片范围以 A4/A5 当前文档为准

> 同步说明（2026-08-29）：技术栈方向仍有效，但本文早期的单 `trips.itinerary JSON`、`POST /api/trips/generate`、`regenerate`、单一 `transport_type` 和默认 Celery/WebSocket 流程已被 [应用代码架构设计.md](应用代码架构设计.md)、[../specs/api-contract.md](../specs/api-contract.md)、[../specs/data-model.md](../specs/data-model.md) 替代。正文中 K-Means 固定分天、3/5/8 星日硬预算、普通天气硬约束、80–120 条“爬虫入库”和旧 Phase/P1/P2 阶段描述均只保留为历史选型背景，不是当前实现要求；现行约束以 ADR-0004，地点与 OD 以 ADR-0018，阶段与路线以 [项目完整路线图](../process/project-roadmap.md) 为准。

---

## 目录

1. M1 MVP 系统架构总览
2. 前端选型
3. 后端语言选型
4. 核心求解器技术选型
5. 数据库选型
6. 外部 API 选型
7. 决策记录（全部已确认）
8. M1 MVP 技术栈汇总
9. 全四阶段技术架构演进预览
10. 风险与缓解

---

## 一、M1 MVP 系统架构总览

```
┌──────────────────────────────────────────────────────────────────┐
│                 前端 (Taro + React 多端)                           │
│  H5 Web │ 微信小程序                                              │
│  目的地选择 │ 大交通输入 │ 景点筛选 │ 行程展示 │ 分享卡片 │ 反馈    │
├──────────────────────────────────────────────────────────────────┤
│                      API 网关层                                   │
│              RESTful API / 微信登录 / 限流                         │
├──────────────────────────────────────────────────────────────────┤
│                    业务服务层                                      │
│  ┌──────────┬──────────┬──────────┬──────────┬──────────┐       │
│  │ 景点服务  │ 行程服务  │ 用户服务  │ 分享服务  │ 数据管道  │       │
│  └──────────┴──────────┴──────────┴──────────┴──────────┘       │
├──────────────────────────────────────────────────────────────────┤
│                 ★ 核心求解器引擎                                   │
│  K-Means地理聚类 → TSP-TW天内排序 → 约束校验 → 天气适配 → 回溯    │
├──────────────────────────────────────────────────────────────────┤
│                     数据层                                        │
│  MySQL(景点/行程/用户) │ Redis(缓存/OD矩阵) │ 腾讯云COS(图片)      │
│  外部API: 高德地图 │ 和风天气 │ 微信开放平台                       │
├──────────────────────────────────────────────────────────────────┤
│                   LLM 可插拔层                                     │
│  DeepSeek(默认) │ Claude │ GPT                                   │
│  职责：行程解释生成、景点数据LLM结构化                              │
└──────────────────────────────────────────────────────────────────┘
```

### M1 核心用户流程

```
选择目的地 → 输入大交通方式+到达/离开时间 → 选择出行日期+模式+人群
    → 浏览景点列表+类型筛选 → 勾选想去的景点
    → 一键生成分日行程 → 查看行程详情（含天气风险提示+室内替代）
    → 不满意？替换景点+重新生成 → 满意？生成分享卡片 → 给出反馈
```

---

## 二、前端选型

### 2.1 决策：Taro + React 多端起步

**✅ 已确认**：M1 直接用 Taro + React，同时出 H5 Web 和微信小程序。

**决策理由**：
1. M1 即可验证完整获客闭环——分享卡片嵌入小程序码 → 扫码 → 新用户注册
2. 微信生态（搜一搜、分享朋友圈）是 M1 冷启动的重要渠道
3. 虽然多端兼容调试增加 20-30% 前端工作量，但后端 FastAPI 和 Python 生态的开发效率可以挤出时间
4. 不存在"M2 迁移重写"的问题，从一开始就是多端架构

### 2.2 Taro 技术栈

| 用途 | 选型 | 说明 |
|------|------|------|
| 框架 | Taro 4 + React 18 + TypeScript | 编译到 H5 + 微信小程序 |
| CSS | TailwindCSS + weapp-tailwindcss | 适配小程序的 Tailwind 插件 |
| 组件库 | NutUI（Taro 官方推荐） | 或 Taro UI，优先选维护活跃的 |
| 地图组件 | Taro 地图组件 + 高德小程序 SDK | H5 端降级为高德 JS API |
| 状态管理 | Zustand | 轻量、跨端兼容 |
| 路由 | Taro 内置路由 | 不需要额外路由库 |
| 请求库 | Taro.request | 或封装 axios（H5 端） |

### 2.3 分享卡片方案

**✅ 已确认**：服务端渲染（Puppeteer）。

- 后端用 Puppeteer 无头浏览器渲染 HTML 模板 → 截图 → 上传腾讯云 COS → 返回图片 URL
- 小程序码由后端调用微信 API 生成，嵌入卡片
- H5 和小程序端展示同一张服务端渲染的图片，保证一致性
- 前端可做低精度即时预览（可选），正式分享走服务端

---

## 三、后端语言选型

### 3.1 决策：Python 3.12 + FastAPI

**✅ 已确认**：Python 3.12 + FastAPI 作为 M1 主后端，Java 暂不使用。

**决策理由**：
1. OR-Tools 的 Python 绑定最成熟，你无 OR 背景，Python 学习曲线最平缓
2. LLM 集成（openai SDK、anthropic SDK）在 Python 生态是一等公民
3. NumPy/scikit-learn 用于地理聚类和 OD 矩阵计算
4. FastAPI 异步 + Pydantic 类型校验，开发速度快
5. M1 并发量低（DAU < 1000），Python 性能完全够用

**Java 未来定位**：M2-M3 若需高并发票务预订、复杂事务管理，可拆出独立 Java 微服务。

### 3.2 Python 技术栈

| 用途 | 选型 | 说明 |
|------|------|------|
| Web 框架 | FastAPI | 异步、自动 OpenAPI 文档、Pydantic 集成 |
| ORM | SQLAlchemy 2.0 + Alembic | 异步支持、数据库迁移 |
| 数据校验 | Pydantic v2 | 与 FastAPI 深度集成 |
| 异步任务 | Celery + Redis | 求解器、爬虫、LLM 调用均为异步任务 |
| LLM 集成 | openai SDK + anthropic SDK | 可插拔架构，配置切换 |
| 科学计算 | NumPy + scikit-learn | 地理聚类 K-Means |
| 爬虫 | httpx + BeautifulSoup + Celery Beat | 定时采集景点数据 |
| Puppeteer | pyppeteer 或 playwright | 分享卡片服务端渲染 |
| 测试 | pytest + httpx | 异步测试支持 |
| 代码质量 | ruff + mypy | 快速 linting + 类型检查 |

---

## 四、核心求解器技术选型

### 4.1 问题定义

> 给定 N 个景点、D 天行程、到达/离开时间锚点（Day 1 有效起始时间、Day N 有效结束时间）、每个景点有开放时间窗、体力消耗值、建议游览时长，景点间有实际交通耗时，在满足（到达/离开时间锚点、地理聚类、每日体力上限、开放时间、天气适配）多约束下，求每日景点序列的最优或近似最优解。

**复杂度定性**：属于**带时间窗和多约束的团队定向问题（TOP-TW 变种）**，NP-hard。当 N=15、D=3 时，搜索空间已远超穷举可行范围。

### 4.2 决策：OR-Tools Routing Solver + scikit-learn K-Means（方案 B）

**✅ 已确认**：M1 采用"先聚类后独立求解"策略。

**M1 分层求解流程**：

```
┌──────────────────────────────────────────────────────────────────┐
│  Step 1: 地理聚类（scikit-learn K-Means）                         │
│  输入：N 个景点的经纬度 + D 天                                   │
│  输出：每个景点归属的 Day 分组                                    │
│  说明：K=D，将 N 个景点按空间距离聚为 D 组                        │
│  降维目的：将全局排序问题降为 D 个独立的子问题                    │
├──────────────────────────────────────────────────────────────────┤
│  Step 2: 天内排序（OR-Tools Routing Solver，每天独立求解）        │
│  输入：当天的景点组 + 景点间交通耗时矩阵 + 开放时间窗 + 游览时长  │
│  输出：当天最优游览顺序（最小化交通耗时）                         │
│  方法：建模为带时间窗的旅行商问题（TSP-TW）                       │
│  - AddDimension(交通耗时, 时间窗) → 累积时间维度                  │
│  - AddTimeWindow(景点i, 开放开始, 开放结束) → 硬约束              │
│  - 首节点 = 到达时间 + 场站到市区耗时                             │
│  - 末节点 = 离开时间 - 场站提前量                                  │
├──────────────────────────────────────────────────────────────────┤
│  Step 3: 约束校验与回溯                                           │
│  检查：                                                           │
│  - 体力预算：sum(当天景点体力消耗) ≤ 模式日预算（3/5/8星）         │
│  - 天气适配：极端天气硬约束排除户外；普通雨/阵雨标记风险           │
│  - 分配均衡性：如果某天景点过多/过少，移动景点到相邻天             │
│  - 不满足 → 回溯调整分组或标记需替换的景点                        │
├──────────────────────────────────────────────────────────────────┤
│  Step 4: 时间填充                                                 │
│  - 在景点间插入缓冲时间（交通耗时 × 1.2 系数）                     │
│  - 插入用餐时段标记（12:00-13:00 / 18:00-19:00）                  │
│  - 生成最终时间表（上午景点 / 下午景点 / 晚间活动）               │
│  - 调用 LLM 为每项安排生成解释理由                                │
└──────────────────────────────────────────────────────────────────┘
```

### 4.3 天气融入策略（方案 C）

**✅ 已确认**：分层处理。

| 天气等级 | 处理方式 | 示例 |
|------|------|------|
| 极端天气（暴雨/台风/暴雪） | **硬约束**：强制排除当天户外景点，替换为室内景点 | 台风预警 → 西湖从行程中移除，替换为博物馆 |
| 普通雨/阵雨 | **软约束**：保留户外景点，但标记风险 + 推荐室内替代 | 小雨 → 西湖保留，标注"⚠️ 当天有小雨，可备选中国伞博物馆" |
| 晴天/多云 | 无影响 | 正常安排 |

天气等级通过和风天气 API 返回的天气类型判断：`暴雨`、`大暴雨`、`特大暴雨`、`台风`、`暴雪` 归为极端天气。

### 4.4 M2 优化方向（备忘）

**⚠️ 标注**：M2 引入住宿位置优化时，重新评估**方案 A（多车辆建模）**。住宿位置与景点日期分配是互耦的——住在哪里影响每天去哪，每天去哪反过来影响最优住宿位置。多车辆建模可以一次性求解"景点分配 + 住宿位置 + 天内排序"的全局最优。

### 4.5 OR-Tools 关键 API 映射

| 问题元素 | OR-Tools 映射 |
|------|------|
| 景点 | `routing.NodeIndex(i)` |
| 景点间交通耗时 | `routing.SetArcCostEvaluatorOfAllVehicles(transit_callback)` |
| 开放时间窗 | `time_dimension.CumulVar(node).SetRange(start, end)` |
| 游览时长（停留） | `transit_callback` 中返回 `travel_time + visit_duration` |
| 到达/离开锚点 | Depot 节点的 `CumulVar` 设置起始/结束时间 |

### 4.6 性能目标与可行性

| 指标 | 目标 | 实现方式 |
|------|------|------|
| 求解时间（N≤20, D≤7） | < 2 分钟 | 每天独立求解，并行计算 |
| 求解时间（N≤12, D≤3，典型场景） | < 30 秒 | 搜索空间小，预期快速收敛 |
| 硬约束检查通过率 | 100% | 自动化校验：闭馆/开放时间、时间锚点、极端天气和真实交通衔接；体力为软约束 |
| 超大问题（N>25） | 降级处理 | 前置提示"建议每日不超过 X 个景点" |

### 4.7 求解器异步执行方案

> 本节是历史方案。A4/A5 已改为 `GenerationIntent + GenerationExecutor`：首切片使用 inline executor 和状态查询，出现性能/并发证据后可替换为 Celery；当前资源路径见 API 契约 V2.0。

```
用户点击"生成行程"
    → POST /api/trips/generate
    → 后端创建 TripTask（status=pending）
    → 返回 task_id 给前端
    → Celery Worker 执行求解器
    → 完成后更新 TripTask（status=completed, result=...）
    → 前端轮询 GET /api/trips/{task_id}/status 或 WebSocket 推送
```

---

## 五、数据库选型

### 5.1 存储方案

| 数据 | 存储 | 说明 |
|------|------|------|
| 景点基础数据（标签、坐标、开放时间、体力消耗、室内外） | **MySQL** | M1 约 80-120 条，爬虫采集 + LLM 结构化 + 人工校准 |
| 用户数据（微信 openid） | **MySQL** | 微信扫码登录，M1 用户量小 |
| 行程数据（行程主表 + 每日安排 + 景点序列） | **MySQL** | JSON 字段存求解器输出的结构化结果 |
| 反馈数据（👍👎 + 可选原因） | **MySQL** | 关联到行程-景点对 |
| 景点间 OD 矩阵（交通耗时、距离） | **Redis** | 预计算缓存，Key: `od:{city}:{from_id}:{to_id}` |
| 天气数据 | **Redis** | 按城市+日期缓存，TTL = 1小时 |
| 分享卡片图片 | **腾讯云 COS** | 服务端 Puppeteer 渲染后上传 |
| Session/Token | **Redis** | JWT 黑名单或 Session 存储 |

### 5.2 是否需要 PostGIS？

**M1 不需要。** 理由：
- M1 的空间计算（地理聚类 K-Means、OD 矩阵）都在求解器内存中完成，不依赖数据库空间扩展
- 景点坐标存 `DECIMAL(10,7)` 字段即可，查询时加载到内存由 NumPy 处理
- M2 住宿区域建议可能需要空间查询，届时再评估是否引入 PostGIS

### 5.3 核心表结构草案

```sql
-- 城市表
CREATE TABLE cities (
    id INT PRIMARY KEY AUTO_INCREMENT,
    name VARCHAR(50) NOT NULL,
    province VARCHAR(50),
    center_lat DECIMAL(10,7),
    center_lng DECIMAL(10,7),
    status TINYINT DEFAULT 1  -- 1=active
);

-- 景点表（M1 核心）
CREATE TABLE attractions (
    id INT PRIMARY KEY AUTO_INCREMENT,
    city_id INT NOT NULL,
    name VARCHAR(100) NOT NULL,
    category ENUM('自然山水','古镇人文','寺庙祈福','城市观景','博物馆','美食街区','网红打卡','亲子乐园','演出演艺'),
    energy_level TINYINT NOT NULL,  -- 1-5 体力消耗
    suggested_duration INT,         -- 建议游览分钟数
    open_time TIME,                 -- 营业开始时间
    close_time TIME,                -- 营业结束时间
    close_day TINYINT DEFAULT 0,    -- 闭馆星期 (0=无, 1-7=周一到周日)
    is_indoor TINYINT DEFAULT 0,    -- 0=室外, 1=室内
    lat DECIMAL(10,7),
    lng DECIMAL(10,7),
    suitable_crowd JSON,            -- ["情侣","亲子","老人","独行"]
    best_season JSON,               -- ["3","4","5","9","10"] 月份
    tags JSON,                      -- 扩展标签
    data_source VARCHAR(50),        -- 数据来源：gaode/baidu_baike/ctrip/manual
    data_verified TINYINT DEFAULT 0,-- 0=未校准, 1=已人工校准
    status TINYINT DEFAULT 1
);

-- 行程主表
CREATE TABLE trips (
    id INT PRIMARY KEY AUTO_INCREMENT,
    user_id INT NOT NULL,
    city_id INT NOT NULL,
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    travel_mode ENUM('speed','normal','leisure'),
    crowd_type ENUM('solo','couple','family','elderly'),
    arrival_time DATETIME,          -- 到达时间
    departure_time DATETIME,        -- 离开时间
    transport_type ENUM('flight','high_speed_rail','train','self_drive','bus'),
    itinerary JSON,                 -- 求解器输出的完整行程
    weather_notes JSON,             -- 天气风险提示
    status ENUM('draft','generated','shared'),
    created_at DATETIME DEFAULT NOW()
);

-- 反馈表
CREATE TABLE feedbacks (
    id INT PRIMARY KEY AUTO_INCREMENT,
    trip_id INT NOT NULL,
    user_id INT NOT NULL,
    attraction_id INT NOT NULL,
    day_index INT NOT NULL,
    rating ENUM('like','dislike'),
    reason VARCHAR(500),
    created_at DATETIME DEFAULT NOW()
);
```

---

## 六、外部 API 选型

### 6.1 API 清单

| 用途 | 选型 | 说明 |
|------|------|------|
| **地图/地理编码** | 高德地图 Web API | 国内数据质量好、文档清晰、免费额度充足 |
| **路径规划/交通耗时** | 高德地图 路径规划 API | 支持驾车/公交/步行多种模式 |
| **天气** | 和风天气 API | 免费版支持 3 天预报，M1 足够 |
| **LLM** | DeepSeek（默认）/ Claude / GPT | 可插拔架构，配置切换 |
| **图片存储** | 腾讯云 COS | 分享卡片图片存储 |
| **微信登录** | 微信开放平台（Web 端）+ 微信小程序登录 | 扫码登录 + 静默登录 |

### 6.2 高德 API 免费额度评估

| API | 免费日调用量 | M1 预估用量 | 是否够用 |
|------|------|------|------|
| 地理编码 | 5000 次/日 | < 100 次/日 | ✅ |
| 路径规划 | 5000 次/日 | 预计算 120×120 = 14400 次（一次性），日常 < 100 次/日 | ✅ 预计算后缓存 |
| 天气查询 | 100000 次/日 | < 50 次/日 | ✅ |

> 预计算 OD 矩阵：M1 1 个城市约 120 个景点，景点对 OD 矩阵为 120×120 ≈ 14400 次路径规划请求。一次性计算后存入 Redis 缓存，后续仅需增量更新。

### 6.3 LLM 可插拔架构

```
┌──────────────────────────────────┐
│         LLMProvider (接口)        │
│  - generate(prompt) → str        │
│  - generate_batch(prompts) → list│
├──────────────────────────────────┤
│  ┌──────────┐ ┌──────────┐ ┌──────────┐
│  │DeepSeek  │ │ Claude   │ │ OpenAI   │
│  │(默认)    │ │          │ │          │
│  └──────────┘ └──────────┘ └──────────┘
└──────────────────────────────────┘
```

通过环境变量 `LLM_PROVIDER=deepseek` 切换，无需改代码。每个 Provider 封装对应 SDK 的调用细节。

---

## 七、决策记录（全部已确认）

| # | 议题 | 决策 | 关键理由 |
|---|------|------|------|
| 1 | 前端形态 | **Taro + React 多端** | M1 同时出 H5 + 小程序，验证完整获客闭环 |
| 2 | LLM 选型 | **可插拔架构**，默认 DeepSeek，可切换 Claude/GPT | 国内优先，保留灵活性 |
| 3 | 部署方案 | **腾讯云** | 与微信小程序生态协同 |
| 4 | 用户认证 | **微信扫码登录** | Web 端开放平台扫码，小程序端静默登录 |
| 5 | 求解器建模 | **M1 方案 B**（K-Means 聚类 + 独立 TSP-TW） | M2 引入住宿优化时重新评估方案 A（多车辆建模） |
| 6 | 天气融入 | **方案 C**（极端天气硬约束，普通雨/阵雨软约束） | 分层处理，兼顾体验底线和用户选择权 |
| 7 | 景点数据 | **爬虫采集 + LLM 结构化 + 人工校准** | 高德 POI + 百度百科为主，定时采集，周级更新 |
| 8 | 分享卡片 | **服务端渲染**（Puppeteer） | 所有端渲染一致，品质可控 |

---

## 八、M1 MVP 技术栈汇总

```
┌──────────────────────────────────────────────────────────────────┐
│  类别          │ 选型                                             │
├──────────────────────────────────────────────────────────────────┤
│  前端框架       │ Taro 4 + React 18 + TypeScript                  │
│  CSS           │ TailwindCSS + weapp-tailwindcss                  │
│  组件库        │ NutUI（Taro 推荐） 或 Taro UI                    │
│  地图组件       │ Taro Map + 高德小程序 SDK / 高德 JS API         │
│  状态管理       │ Zustand                                         │
│  分享卡片       │ 服务端渲染（Puppeteer）→ 腾讯云 COS             │
│  后端框架       │ Python 3.12 + FastAPI                           │
│  ORM           │ SQLAlchemy 2.0 + Alembic                        │
│  数据校验       │ Pydantic v2                                     │
│  异步任务       │ Celery + Redis                                  │
│  核心求解器     │ OR-Tools + scikit-learn                         │
│  爬虫          │ httpx + BeautifulSoup + Celery Beat              │
│  LLM           │ 可插拔：DeepSeek(默认) / Claude / GPT            │
│  Puppeteer     │ playwright 或 pyppeteer                          │
│  数据库        │ MySQL 8.0 + Redis                               │
│  地图 API       │ 高德地图 Web API                                │
│  天气 API       │ 和风天气 API                                    │
│  对象存储       │ 腾讯云 COS                                      │
│  微信登录       │ 微信开放平台 + 微信小程序登录 API                │
│  部署          │ Docker Compose + 腾讯云 CVM                      │
│  CI/CD         │ GitHub Actions                                  │
│  代码质量       │ ruff + mypy                                     │
│  测试          │ pytest + httpx                                  │
└──────────────────────────────────────────────────────────────────┘
```

### 8.1 部署架构

```
腾讯云 CVM（单机 Docker Compose）
├── nginx            (反向代理 + 静态资源)
├── fastapi          (API 服务)
├── celery-worker    (求解器 + 爬虫 + LLM 调用)
├── celery-beat      (定时任务：爬虫、天气刷新)
├── puppeteer        (分享卡片渲染服务)
├── mysql            (或使用腾讯云 CDB)
└── redis            (或使用腾讯云 Redis)
```

---

## 九、全四阶段技术架构演进预览

```
M1 (当前)             M2                    M3                    M4
───────              ────                  ────                  ────
前端
Taro 多端      →     Taro 多端         →   原生 App？          →  全端覆盖
(H5+小程序)           + 更多模板           (RN/Flutter)

后端
FastAPI        →     FastAPI            →   微服务拆分          →  Event-Driven
单体                   + 知识图谱服务       + 票务服务(Java?)     + 偏好学习服务
                      + 评论管道服务       + 实时推送服务         + 游记生成服务

求解器
OR-Tools       →     + 方案A多车辆建模   →   + 动态重排引擎      →  + 长期偏好学习
K-Means（方案B）      + 住宿位置优化          + 拥挤度预测         + 图神经网络？
                      + 同质化检测           + 连锁更新
                      + 交通接驳优化

数据层
MySQL          →     + 知识图谱(Neo4j?)  →   + 时序数据库        →  + 向量数据库
Redis                + 评论摘要库            + Kafka 消息队列      + 用户画像存储
COS                  + Elasticsearch        + 实时数据管道

外部API
高德地图        →     多源评论爬虫          →   票务联盟API         →  UGC数据管道
和风天气              多平台比价API             人流数据API
DeepSeek              交通票务API
微信开放平台
```

---

## 十、风险与缓解

| 风险 | 严重程度 | 缓解措施 |
|------|------|------|
| **Python 性能瓶颈** | 低 | M1 用户量小，FastAPI async 足够；求解器是计算密集型，Celery 异步隔离 |
| **OR-Tools 学习曲线** | 中 | 官方有 VRPTW Tutorial，预计 1-2 周可上手；社区和 Stack Overflow 活跃 |
| **Taro 多端兼容调试** | 中 | 优先保证 H5 端核心流程，小程序端逐步适配；使用 NutUI 等 Taro 原生组件库减少兼容问题 |
| **单人开发 4 个月交付** | 中 | 后端 FastAPI 开发效率高；景点数据爬虫自动化减少人工标注；不做 M2+ 功能 |
| **高德 API 费用** | 低 | 初期用量小，免费额度内；OD 矩阵预计算后缓存 |
| **LLM API 不稳定** | 低 | 可插拔架构，DeepSeek 不可用时切换 Claude/GPT；行程解释非实时，可重试+降级 |
| **求解器效果不达预期** | 高 | 设置硬性质量门（硬约束 100% 通过），M1 上线前用户测试 n≥20 验证 |
| **景点数据质量** | 中 | 聚焦 1 个城市，爬虫初筛 + LLM 结构化 + 人工抽检校准三层保障 |
| **M1 范围膨胀** | 中 | 严格用 MVP 决策逻辑约束："缺了它核心假设还能验证吗？" |
| **微信登录审核** | 低 | 微信开放平台网站应用需企业资质，提前准备；小程序端登录无门槛 |
| **Puppeteer 内存开销** | 低 | 独立容器 ~300MB，M1 并发低，单实例足够；可按需扩缩 |

---

## 十一、M1 开发里程碑建议

```
Month 1 ─── 基础设施 + 数据建设
  Week 1-2: 项目脚手架（Taro + FastAPI + Docker）、数据库建表
  Week 3-4: 爬虫管道（高德 POI + 百度百科）→ LLM 结构化 → 景点数据入库
            高德 OD 矩阵预计算 → Redis 缓存

Month 2 ─── 核心求解器
  Week 1-2: OR-Tools 学习 + 原型验证（TSP-TW 小规模测试）
  Week 3-4: 分层求解器实现（K-Means 聚类 + TSP-TW + 约束校验 + 回溯）
            天气适配 + 室内替代匹配

Month 3 ─── 前后端业务开发
  Week 1-2: API 开发（景点、行程、反馈、用户）、微信登录对接
  Week 3-4: 前端开发（景点浏览+筛选 + 行程生成 + 行程展示 + 反馈）

Month 4 ─── 分享 + 打磨 + 测试
  Week 1-2: 分享卡片（Puppeteer 渲染 + 小程序码 + 模板）、LLM 行程解释
  Week 3-4: 用户测试（n≥20）、Bug 修复、性能优化、上线准备
```

---

**文档结束**

---

*V1.1 变更说明：所有第七节待决策事项已确认。前端改为 Taro 多端、LLM 改为可插拔架构、部署改为腾讯云、认证改为微信扫码登录、求解器确认方案 B + 天气方案 C、景点数据改为爬虫+LLM+人工校准、分享卡片改为服务端渲染。新增第十一节 M1 开发里程碑建议。*

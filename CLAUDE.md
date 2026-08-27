# trave_agent — 项目上下文（Claude 每次会话必读）

## 一句话定位

旅行助手：输入目的地，自动规划旅行路线，搞定衣食住行。核心命题是「**AI 求解器排的行程比人排更合理**」。

## 当前阶段

**M1 MVP（4 个月）**：行程骨架验证。只做 8 项功能，验证单一核心假设 **H3**。不做推荐、不做信息聚合、不做社区。

**Gate 6 求解器技术验证已通过，当前处于 M1 应用产品化 A6-8.1 收口。** 求解器核心实现已阶段性完成，M1 对外契约已稳定并版本化；A1–A5 设计和首个浏览器可操作纵向切片已经完成。7 个杭州路线点已由发布责任人接受并生成独立 `human_verified` 坐标版本，新版本 42/42 严格高德有向 OD 已重建；新 OD 暴露的“单日间节点 + 固定晚间段”下午空白已按 ADR-0015 修复并升级到 `constraints-p1-v5`。和风三日天气链路、不可变 JSON 发布 Provider、正式合并器和生产 fail-fast 组合根已完成离线验证；正式发布仍等待和风真实凭证/响应、正式 bundle 和配额治理。`spike/` 是历史验证原型，不是生产实现模板。
完整假设账本见 [docs/assumptions.md](docs/assumptions.md)。

## 技术栈速览

| 层 | 选型 |
|---|---|
| 前端 | Taro 4 + React 18 + TypeScript（H5 + 微信小程序），Zustand |
| 后端 | Python 3.12 + FastAPI + SQLAlchemy 2.0 + Celery + Redis |
| 核心求解器 | OR-Tools（M1 分层：已发布 OD 的确定性聚类与日负载均衡 → TSP-TW 天内排序 → 约束校验 → 时间填充） |
| 存储 | MySQL 8 + Redis + 腾讯云 COS |
| LLM | 可插拔（DeepSeek 默认 / Claude / GPT） |
| 外部 API | 高德地图、和风天气、微信开放平台 |

## 四条核心原则（不可违背）

1. **大模型做「软」的事，引擎做「硬」的事**：LLM 负责理解/表达/摘要/解释；求解、校验、约束、路由由确定性引擎负责。
2. **硬约束 100% 通过**：C1 闭馆日、C2 入园时间窗、C4 时间锚点、C5 极端天气、C6 交通衔接违反数必须为 0；体力是软约束，不得硬拦。
3. **数据质量门禁**：景点数据字段必须带 `source` + `data_verified`；硬事实（开放时间/价格/闭馆日）只从结构化 DB 读，**LLM 不得生成**。
4. **假设可追溯**：任何代码/测试/文档都回溯到 [docs/assumptions.md](docs/assumptions.md) 的 `H-x` 编号或需求编号。

## 知识库导航

| 路径 | 内容 |
|---|---|
| [docs/assumptions.md](docs/assumptions.md) | ★ 假设登记册（工作流账本，状态机） |
| [docs/00-index.md](docs/00-index.md) | 文档地图 + 阅读顺序 |
| [docs/product/](docs/product/) | 产品文档、技术选型文档 |
| [docs/domain/](docs/domain/) | 旅行领域规范（体力消耗/景点类型/行程模式/开放时间数据规范）——**硬事实唯一来源** |
| [docs/decisions/](docs/decisions/) | ADR 架构决策记录 |
| [docs/specs/](docs/specs/) | 需求规格 + Given/When/Then 验收标准 |
| [docs/research/](docs/research/) | 用户研究计划 + 结论 |
| [docs/test/](docs/test/) | 测试方案 + Golden Cases |

## 工作流（假设驱动的 AI 协作开发）

```
G0 假设登记 → G1 用户研究 → G2 需求规格化 → G3 技术 Spike（风险前置）
→ G4 详细设计 + ADR → G5 约束 TDD 实现 ⇄ G6 分层测试 → G7 假设复盘
```

每个阶段有退出准则（Gate），不满足不进下一阶段。最不确定的（求解器、数据质量、用户需求）**最先验证**，不按自然实现顺序排。

Gate 定义、权威来源优先级与冲突处理见 [docs/process/gates.md](docs/process/gates.md)。若资料冲突，停止实现并报告冲突，不得自行选用旧版本。

## M1 最终约束基线（ADR-0004）

| 类型 | 编号 | 约束 |
|---|---|---|
| 硬 | C1 | `weekday ∈ close_days` 时不可排，支持节假日例外 |
| 硬 | C2 | `arrival ∈ [open, min(last_entry, close − 0.6×duration)]` |
| 硬 | C4 | 首日到达、末日离开与返程时间锚点 |
| 硬 | C5 | 极端天气排除室外景点 |
| 硬 | C6 | 基于 OD 耗时的真实交通衔接 |
| 软 | S1 | 实际游览不足建议时长时提示，默认最低比例 60% |
| 软 | S2 | 高体力景点分天均衡 + 节奏提示，不设置 3/5/8 星硬上限 |

当前天内目标函数为 `min Σ travel`。默认分天先保护 OD 近邻，再平衡每日景点数量和建议游览负载；体力均衡仍是分天启发式，不进入天内目标函数。任何改变目标函数或恢复体力硬上限的提议都必须新写 ADR。

## 关键约定

- 求解器改动必须附带对应约束单测（详见 [.claude/rules/](.claude/rules/)）
- 算法/数据改动必须跑 Golden Case 回归
- 新增第三方依赖需写 ADR
- 每个 PR 关联 `H-x` 编号
- 测试：pytest；lint/type：ruff + mypy

## 权威来源简表

发生冲突时按以下顺序判断：最新且已接受的 ADR → 当前 Accepted 规格 → 领域规范/数据模型 → 假设登记册 → `.claude` rules/skills/agents → 历史产品文档与 Spike。`.claude` 控制文件必须追随 ADR 和规格，不能覆盖它们。

## 团队背景（影响节奏，不要忽略）

- **团队无 OR / 运筹背景** → 求解器相关任务时间盒放宽，优先用 Spike 验证可行性，再投入实现。
- **M1 可能单人开发** → 简化流程，倾向「可丢弃的 Spike」和「自包含、零依赖的原型」。
- **杭州先行**：M1 仅 1 个目的地城市，景点 80–120 个，人工标注为主 + LLM 辅助抽取 + 人工抽检。

## 当前最该做的三件事（按优先级）

1. 使用新审核 OD 完成 `constraints-p1-v5` 单日间节点下午展开的全量、Golden、降级、接近度、数据和性能回归，并确认历史 Revision 不覆盖。
2. 在 `.env` 配置和风 Key 与项目 API Host，执行真实三日天气构建，合并正式杭州 OD/天气 Published Snapshot，通过生产组合根、FastAPI 和 Chrome 回放。
3. 补齐配额看板、熔断、跨机器缓存与旧快照继续服务策略，再进入 A6-8.2 真实 MySQL 与部署恢复。

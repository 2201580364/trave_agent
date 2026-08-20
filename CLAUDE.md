# trave_agent — 项目上下文（Claude 每次会话必读）

## 一句话定位

旅行助手：输入目的地，自动规划旅行路线，搞定衣食住行。核心命题是「**AI 求解器排的行程比人排更合理**」。

## 当前阶段

**P1 MVP（4 个月）**：行程骨架验证。只做 8 项功能，验证单一核心假设 **H3**。不做推荐、不做信息聚合、不做社区。
完整假设账本见 [docs/assumptions.md](docs/assumptions.md)。

## 技术栈速览

| 层 | 选型 |
|---|---|
| 前端 | Taro 4 + React 18 + TypeScript（H5 + 微信小程序），Zustand |
| 后端 | Python 3.12 + FastAPI + SQLAlchemy 2.0 + Celery + Redis |
| 核心求解器 | OR-Tools + scikit-learn（P1 分层：K-Means 聚类 → TSP-TW 天内排序 → 约束校验 → 时间填充） |
| 存储 | MySQL 8 + Redis + 腾讯云 COS |
| LLM | 可插拔（DeepSeek 默认 / Claude / GPT） |
| 外部 API | 高德地图、和风天气、微信开放平台 |

## 四条核心原则（不可违背）

1. **大模型做「软」的事，引擎做「硬」的事**：LLM 负责理解/表达/摘要/解释；求解、校验、约束、路由由确定性引擎负责。
2. **硬约束 100% 通过**：开放时间、体力预算、时间锚点是底线，「不错」优先于「更好」。
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

## 关键约定

- 求解器改动必须附带对应约束单测（详见 [.claude/rules/](.claude/rules/)）
- 算法/数据改动必须跑 Golden Case 回归
- 新增第三方依赖需写 ADR
- 每个 PR 关联 `H-x` 编号
- 测试：pytest；lint/type：ruff + mypy

## 团队背景（影响节奏，不要忽略）

- **团队无 OR / 运筹背景** → 求解器相关任务时间盒放宽，优先用 Spike 验证可行性，再投入实现。
- **P1 可能单人开发** → 简化流程，倾向「可丢弃的 Spike」和「自包含、零依赖的原型」。
- **杭州先行**：P1 仅 1 个目的地城市，景点 80–120 个，人工标注为主 + LLM 辅助抽取 + 人工抽检。

## 当前最该做的三件事（按优先级）

1. G3 Solver Spike + Data Quality Spike（验证最不确定的东西，见 [spike/solver_spike/](spike/solver_spike/)）
2. G2 把「一键生成分日行程」写成带 Given/When/Then 的规格 + 第一条约束单测
3. 数据质量门禁落地（source/verified 覆盖 + 校验测试）

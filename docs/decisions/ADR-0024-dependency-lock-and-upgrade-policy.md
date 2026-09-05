# ADR-0024：依赖锁定与升级政策

- **状态**：已接受
- **日期**：2026-09-05
- **决策者**：trave_agent 单人开发（AI 协作）
- **关联任务**：transformation-plan S4-1
- **关联假设**：无直接假设；服务于 R0.3 部署环境可复现前提

## 背景与问题

pyproject.toml 的依赖声明为区间约束（如 `fastapi>=0.111,<1`），每次安装解析结果可能不同：

1. **环境不可复现**：本地 venv、CI、R0.3 服务器三者解析出的版本可能漂移；服务器 MySQL 迁移（0003→0015）前的下一次应用发布，必须在版本确定的代码基线上执行。
2. **升级无纪律**：OR-Tools / SQLAlchemy / FastAPI 属于行为敏感依赖（求解器数值与调度行为、ORM 映射与迁移语义、路由/校验行为），静默升级可能改变 golden case 输出而无人在意。
3. **CI 已跑 golden cases（Gate 6）**：恰好构成升级回归的机器护栏，升级纪律可以低成本落地。

## 决策

**用 uv 锁定全量依赖，升级必须走显式流程**：

1. **锁定**：`uv.lock`（141 包）提交入库，是 Python 依赖的唯一权威版本清单。新环境安装方式为 `uv sync --frozen`（或 `pip install -e .` 由 lock 派生的等价流程）；禁止在未更新 lock 的情况下引入新依赖。
2. **升级流程（必须逐项执行）**：
   1. 修改 `pyproject.toml` 区间或执行 `uv lock --upgrade-package <name>`；
   2. 本地跑全量 `pytest`（465+ 基线）；
   3. 跑 `python scripts/run_golden_cases.py`（Gate 6 全过，8/8 基线）；
   4. golden 输出有任何差异 → 停止，写 ADR 说明行为变化是否预期；
   5. lock 文件变更与 ADR 同一提交边界。
3. **行为敏感依赖清单**（升级从严）：`ortools`、`sqlalchemy`、`alembic`、`fastapi`。其余依赖升级仍须全量回归，但不要求单独 ADR（golden 差异兜底）。
4. **major/minor 策略**：区间约束保持现状（服务安全修复的自动 minor/patch 进入 lock 需走上述流程）；不做自动升级机器人。

## 备选方案与权衡

| 方案 | 优点 | 缺点 | 结论 |
|---|---|---|---|
| uv lock（本决策） | 快（本机 40s 解析 55 包）；`--frozen` 一步装成；同时管理 dev extras | 引入 uv 工具依赖（团队需安装） | ✅ 选择 |
| pip-tools（requirements.txt + hash） | 纯 pip 生态 | 双文件同步繁琐；解析慢 | 备选保留 |
| 不锁定，维持区间约束 | 零成本 | 服务器/CI/本地漂移，R0.3 前风险不可控 | ❌ 否决 |

## 后果

- **正面**：R0.3 服务器部署可按 lock 精确复装；升级行为变化 100% 被 golden 护栏拦截；CI 与本地版本一致性有据可查。
- **负面/代价**：每次升级多 2 条命令与一次全量回归（约 5 分钟）；lock 文件约 242KB 入库。
- **技术债务**：CI 当前 `pip install -e ".[dev]"` 未走 `uv sync --frozen`（uv 在 GitHub Actions runner 可用，后续 CI job 可切换，暂不阻塞）。

## 何时推翻重议（触发条件）

- uv 工具链维护停滞或与团队其他项目工具冲突；
- 出现需要跨 Python 多版本矩阵锁定的需求（uv 支持多环境 lock，届时改为 per-version lock）；
- 引入 monorepo 多包结构需要 workspace 级锁定。

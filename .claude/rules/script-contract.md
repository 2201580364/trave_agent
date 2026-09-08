# 脚本契约与工具安全分级

**适用**：`scripts/` 目录下所有面向仓库工作流的可执行脚本，以及「哪些脚本可以交给 AI/模型直接调用」的安全边界。制定于 S5-1（transformation-plan），与 `git-safety.md` 第三节联动。

## 一、脚本契约（所有新脚本与改造脚本必须满足）

1. **稳定退出码**：`0` = 成功通过；`1` = 运行错误（输入不存在、参数非法、异常崩溃）；`2` = 明确的检查失败/门禁违规（脚本本身正常运行，但被检对象不达标）。退出码一经发布即视为对外契约，不得变更含义。
2. **JSON 输出（`--json`）**：所有报告/校验类脚本必须支持 `--json` 标志，输出单一合法 JSON 对象到 stdout（人类可读模式可以并存为默认）。JSON 必须含 `status`（`ok` / `failed` / `error` 之一）或等价的布尔判定字段。写入类脚本的结果摘要同样适用。
3. **fail-closed**：校验遇到歧义、缺数据、解析失败时按失败处理（退出非 0），不得静默放行。
4. **幂等**：同一输入重复运行产生相同结果；写入类脚本的重跑不得覆盖人工已审核/已修改的数据（见 `import_candidate_revisions.py` 的 pristine-import 判定为范本）。
5. **写操作必须 `--dry-run`**：任何会修改数据库、文件或外部状态的脚本必须实现 `--dry-run`（默认或在显式非 dry-run 标志下才落盘），dry-run 输出「将要执行的操作清单」且退出码语义不变。
6. **输出副作用声明**：脚本默认输出路径写入 `var/`（gitignored），不得写 `docs/`（机器再生产物不入文档库，见 file-management.md）。
7. **Windows 兼容**：路径用 `pathlib`，不在脚本内 hardcode 反斜杠；打印中文确保 `encoding="utf-8"`。

## 二、工具安全三级分类

| 级别 | 定义 | 调用策略 |
|---|---|---|
| **L1 只读类** | 不修改任何持久状态：审计、报告、校验、只读查询 | 可直接给模型/AI 会话调用，解析 JSON 即可 |
| **L2 写入类** | 修改数据库/文件/外部系统，但可逆或可审计：导入、快照构建、格式化写入 | 必须 `--dry-run` 预览 + 用户显式确认后才实跑 |
| **L3 破坏类** | 删除、清空、不可逆覆盖、批量破坏性变更 | **永不进模型工具面**；一次性使用，用完即删或存档到受控目录 |

未登记分级的脚本默认按 **L2** 处理（dry-run + 显式确认）；无法提供 dry-run 的写入脚本视为 L3。

## 三、scripts/ 现状分级登记（2026-09-07，S5-3 首批复查）

### L1 只读类（可直接给模型）

| 脚本 | 用途 | 契约状态 |
|---|---|---|
| `report_research_readiness.py` | 研究目录就绪报告 | 已达标（--format json，只读） |
| `audit_catalog_boundaries.py` | 目录边界审计 | 已达标（默认 JSON，退出码 0/2） |
| `validate_candidate_catalog.py` | 候选目录与覆盖矩阵校验 | 已达标（--json；0/1/2：输入缺失=1，校验违规=2。2026-09-07 S5-3 修复 SourceRegistryError 未捕获导致崩溃退出 1 的缺陷） |
| `validate_source_registry.py` | 来源注册与字段字典校验 | 待复查（S5 后续批次） |
| `run_closeness_report.py` | 接近度报告 | 待复查 |
| `run_gate7_report.py` | Gate 7 证据报告 | 待复查 |
| `check_docs.py` | 文档门禁 | 已达标（0/1/2 + --json） |
| `check_layering.py` | 分层断言 | 已达标（0/1/2 + 契约自测） |
| `check_api_contract.py` | OpenAPI 快照与 api-contract 契约 diff 门禁（S8-2） | 已达标（0=通过/1=输入错误/2=code-only 漂移 + --json；contract-only 为信息性含计划端点；CI backend job 已集成） |
| `export_openapi_schema.py` | 离线导出 FastAPI OpenAPI 快照（S8-2） | 已达标（写 var/ 属契约第 6 条允许输出；--json + 0/1；CI 与本地均只写 gitignored 路径，无其他副作用） |
| `sync_agents_docs.py` | AGENTS.md 派生 CLAUDE.md | 特例：写入类但目标文件固定、可重跑（幂等派生），按 L2 收窄为「改 AGENTS.md 后必跑」 |

### L2 写入类（dry-run + 显式确认）

| 脚本 | 用途 | 契约状态 |
|---|---|---|
| `import_candidate_revisions.py` | 候选目录导入 staging | 已达标（--dry-run + 幂等 pristine 判定；2026-09-07 S5-3 补 --json + 修复空库 dry-run 崩溃） |
| `run_golden_cases.py` | Golden 回归 + 报告落盘 var/ | 已达标（报告写 var/reports/，2026-09-07 S5-3 补 --json + stdout JSON） |
| `prepare_candidate_projections.py` | 候选 Projection 准备 | 待改造（后续批次） |
| `init_isolated_catalog_db.py` | 隔离目录库初始化 | 待改造（注意：重建本地库，有覆盖语义） |
| `run_data_validation.py` | 数据校验套件 | 待复查 |
| `run_degradation_cases.py` | 降级用例 | 待复查（报告落 var/ 即 L2-lite） |
| `run_solver_benchmark.py` / `run_solver_contract.py` | 求解器基准/契约 | 待复查 |
| `lock_gate7_environment.py` | 环境锁定 manifest | 待复查（写 var/，接近 L2-lite） |
| `run_local_dev.py` / `run_published_app.py` | 本地/发布应用启动 | 长驻进程类，不适用 --json 契约，按需人工调用 |
| `show_provider_governance.py` | Provider 治理展示 | 待复查（大概率 L1） |

### L3 破坏类

当前 `scripts/` 无 L3 脚本。新增删除/清空/不可逆覆盖类脚本时：先在本表登记、说明一次性用途与销毁计划，且**不得**提供 dry-run 之外的任何自动化路径。

## 四、契约测试要求（S5-4 起）

每个达标脚本在 `tests/scripts/` 配最小契约测试：

1. 成功路径：合法输入退出码 0，`--json` 输出可 `json.loads` 且含判定字段；
2. 失败路径：构造违规输入（缺失文件/非法数据）退出码 1 或 2 且非 0；
3. 写入类：`--dry-run` 下不产生持久变更。

范本：`tests/scripts/test_check_docs.py`、`tests/scripts/test_script_contracts.py`。

## 五、维护约定

- 新增脚本时必须在本文件「现状分级登记」表登记级别与契约状态，未登记视为 L2；
- 分级或契约变更（如 L2→L1）须同步更新本表并跑 `python scripts/check_docs.py`；
- S5-3 之后的改造批次沿「复查 → 登记 → 达标改造 → 契约测试」顺序滚动推进，不追求一次全量。

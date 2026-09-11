# CI 排查指引（S3 产出）

> 适用：`.github/workflows/ci.yml` 三 job（backend / admin-web / frontend）失败时的定位路径。

## CI 结构速查

| Job | 内容 | 本地等价命令 |
|---|---|---|
| backend | uv 锁定安装 + ruff + pytest + golden + 分层 + OpenAPI + 文档门禁 | 见下文逐条 |
| admin-web | npm ci → 下载 backend OpenAPI → 生成类型差异检查 → typecheck → vitest → build | 在 `admin-web/` 下执行 |
| frontend | npm ci --legacy-peer-deps → typecheck → vitest | 在 `frontend/` 下执行 |

## backend job 失败排查

先使用 Python 3.12，安装 CI 固定版本 `uv==0.8.15`，执行 `uv sync --locked --extra dev`。
`--locked` 同时检查 pyproject 与 lock 一致性，不允许自动更新锁文件；`dev` 是 optional extra，必须显式启用。
后续检查均使用 `uv run --no-sync`，保证不会在每步重新解析或修改环境。CI 不再用区间依赖直接安装项目。
本地已有环境同步可能卸载包；遵守 git-safety 的删除前确认规则，或为本次验证指定一个全新的 `UV_PROJECT_ENVIRONMENT` 目录。
Windows 子进程的中文 JSON 输出需要 `PYTHONUTF8=1`。

按步骤顺序对照：

1. **Ruff 失败**
   ```bash
   uv run --no-sync ruff check src/ scripts/ tests/
   ```
   看 `--statistics` 聚类；E501 用 `ruff format <file>` 自动修（注意先确认无语义敏感的手写格式）；其余按提示手工修。
   仓库口径：B008 已在 pyproject 全局豁免（FastAPI `Depends()`/`Query()` 官方惯用法）。

2. **Pytest 失败**
   ```bash
   uv run --no-sync pytest  # 全量
   uv run --no-sync pytest tests/application/test_xxx.py::test_case  # 单用例
   ```
   已知 flaky：Windows 本地偶发 `WinError 10055`（临时套接字耗尽，TestClient 相关）——隔离复跑同一用例即可判定；CI（Linux）不受影响。

3. **Golden cases 失败（Gate 6）**
   ```bash
   uv run --no-sync python scripts/run_golden_cases.py --output var/ci/golden-report.json
   ```
   报告 JSON 里 `gate_passed=false` 时看 `cases[].failure_reason`。Golden 是行为契约：**先确认是改进还是回归**——回归就修代码；确属预期变更才改基准，且必须走 ADR。

4. **Layering assertions 失败**
   ```bash
   uv run --no-sync python scripts/check_layering.py
   ```
   四条规则：domain 不得 import 框架；solver 不得 import infrastructure；依赖只能指向更内层；interfaces 是叶子不可被 import。组合根豁免名单在脚本头部 `INFRA_EXEMPT_FILES`（新增组合根需登记）。

5. **Docs gate 失败**
   ```bash
   uv run --no-sync python scripts/check_docs.py
   ```
   常见：多文件声明了不一致的「当前节点」——只允许在 `docs/process/CURRENT.md` 声明，其余文件用指针表述；ADR 编号冲突；rules 引用了不存在的 ADR。

## admin-web job 失败排查

admin-web 依赖 backend 成功，下载其 `openapi-schema` artifact 到 `var/reports/`，执行 `npm run generate-api-types` 后用 `git diff --exit-code -- src/api/api-schema.d.ts` 拦截漂移。
因此后端失败时 admin-web 会显示 skipped，应先修后端。不能用非锁定环境生成的 schema 覆盖类型文件来消除差异。
该 git diff 检查用于提交后的 CI；本地当前工作区有意更新生成文件时，使用同一 schema 再生成到 `var/reports/` 并比较内容来验证确定性。


```bash
cd admin-web
npm ci            # 若 lockfile 与 package.json 不一致会在这里失败
npm run typecheck # tsc -b
npm test          # vitest run（无 watch）
npm run build     # vite build
```

注意：历史提交中 `admin-web/package-lock.json` 曾为 0 字节（2026-09-05 由 npm install 重新生成）；CI 的 `cache: npm` 依赖 lockfile 有效。

## frontend job 失败排查

```bash
cd frontend
npm ci --legacy-peer-deps
npm run typecheck
npm test
```

frontend 安装必须带 `--legacy-peer-deps`，与现有 lock 的生成方式一致：Taro 的可选 Vite peer 与 Vitest 使用版本冲突，实际 H5 构建走 webpack5。该选项不更新锁文件。
`npm ci` 会清空现有 node_modules，只在新 runner/已确认的环境执行；本地依赖齐全时直接运行 typecheck/test。

## 提交前自查清单

```bash
uv run --no-sync ruff check src/ scripts/ tests/
uv run --no-sync pytest
uv run --no-sync python scripts/run_golden_cases.py --output var/ci/golden-report.json
uv run --no-sync python scripts/check_layering.py
uv run --no-sync python scripts/export_openapi_schema.py --output var/ci/openapi-schema.json
uv run --no-sync python scripts/check_api_contract.py --schema var/ci/openapi-schema.json
uv run --no-sync python scripts/check_docs.py
```

全绿再推。golden 报告等临时产物不要提交（`var/` 已在 .gitignore）。

## 已知债务（不阻塞 CI，分批清偿见 transformation-plan S7）

- 全仓 strict mypy 存量错误（见 CURRENT.md 活跃风险）——CI 暂不跑 mypy 全量；新增文件建议本地 `mypy <file>` 自查。
- `ruff format` 历史漂移（103 文件未格式化）——CI 的 format 检查为 non-blocking，新文件建议 `ruff format <file>` 后再提交。

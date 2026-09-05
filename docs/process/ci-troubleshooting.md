# CI 排查指引（S3 产出）

> 适用：`.github/workflows/ci.yml` 三 job（backend / admin-web / frontend）失败时的定位路径。

## CI 结构速查

| Job | 内容 | 本地等价命令 |
|---|---|---|
| backend | ruff check + pytest + golden cases + 分层断言 + 文档门禁 | 见下文逐条 |
| admin-web | npm ci → typecheck → vitest → build | 在 `admin-web/` 下执行 |
| frontend | npm ci → typecheck | 在 `frontend/` 下执行 |

## backend job 失败排查

按步骤顺序对照（CI 与本地命令完全一致，先本地复现再修）：

1. **Ruff 失败**
   ```bash
   ruff check src/ scripts/ tests/
   ```
   看 `--statistics` 聚类；E501 用 `ruff format <file>` 自动修（注意先确认无语义敏感的手写格式）；其余按提示手工修。
   仓库口径：B008 已在 pyproject 全局豁免（FastAPI `Depends()`/`Query()` 官方惯用法）。

2. **Pytest 失败**
   ```bash
   pytest  # 全量
   pytest tests/application/test_xxx.py::test_case  # 单用例
   ```
   已知 flaky：Windows 本地偶发 `WinError 10055`（临时套接字耗尽，TestClient 相关）——隔离复跑同一用例即可判定；CI（Linux）不受影响。

3. **Golden cases 失败（Gate 6）**
   ```bash
   python scripts/run_golden_cases.py --output var/ci/golden-report.json
   ```
   报告 JSON 里 `gate_passed=false` 时看 `cases[].failure_reason`。Golden 是行为契约：**先确认是改进还是回归**——回归就修代码；确属预期变更才改基准，且必须走 ADR。

4. **Layering assertions 失败**
   ```bash
   python scripts/check_layering.py
   ```
   四条规则：domain 不得 import 框架；solver 不得 import infrastructure；依赖只能指向更内层；interfaces 是叶子不可被 import。组合根豁免名单在脚本头部 `INFRA_EXEMPT_FILES`（新增组合根需登记）。

5. **Docs gate 失败**
   ```bash
   python scripts/check_docs.py
   ```
   常见：多文件声明了不一致的「当前节点」——只允许在 `docs/process/CURRENT.md` 声明，其余文件用指针表述；ADR 编号冲突；rules 引用了不存在的 ADR。

## admin-web job 失败排查

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
npm ci
npm run typecheck
```

## 提交前自查清单

```bash
ruff check src/ scripts/ tests/
pytest
python scripts/run_golden_cases.py --output var/ci/golden-report.json && rm -rf var/ci
python scripts/check_layering.py
python scripts/check_docs.py
python scripts/sync_agents_docs.py --check
```

全绿再推。golden 报告等临时产物不要提交（`var/` 已在 .gitignore）。

## 已知债务（不阻塞 CI，分批清偿见 transformation-plan S7）

- 全仓 strict mypy 存量错误（见 CURRENT.md 活跃风险）——CI 暂不跑 mypy 全量；新增文件建议本地 `mypy <file>` 自查。
- `ruff format` 历史漂移（103 文件未格式化）——CI 的 format 检查为 non-blocking，新文件建议 `ruff format <file>` 后再提交。

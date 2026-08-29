# Gate 7 研究环境锁定规范

- 文档版本：V1.2
- 日期：2026-08-29
- 产品里程碑：M1 — 行程骨架验证
- Gate：G7-R0.1
- 当前结论：锁定机制已实现；R0.2 杭州研究数据、R0.3 服务器 H5 和 R0.4 dry run 未完成，实际形成性研究环境尚未锁定

## 1. 为什么必须锁定

Gate 7 收集的是专家和目标用户证据。若不同 session 临时切换代码、数据、求解器参数、数据库迁移或前端构建，同一指标将不再具有共同解释口径。研究环境 manifest 用一个非敏感 JSON 对象固定这些事实，并让每份 evidence 通过环境 ID 和 manifest SHA-256 精确引用它。

环境锁定不表示应用已经正式生产发布，也不表示 Gate 7 已通过。它只证明指定研究批次使用的技术环境可追溯且在收集前固定。

## 2. Manifest 内容

Schema 为 `gate7-research-environment-v1`，固定以下内容：

| 类别 | 字段 |
|---|---|
| 研究身份 | `study_environment_id`、`study_phase`、`generated_at`、`status` |
| 源代码 | `git_commit`、`git_tree_clean`、`app_version` |
| Protocol | `protocol_id`、`protocol_version`、`protocol_sha256` |
| 求解契约 | `result_schema_version`、`solver_version`、`constraint_version`、`parameter_version` |
| 数据 | `city_id`、`data_snapshot_version`、`data_snapshot_kind`、`data_snapshot_sha256` |
| 运行构建 | `database_revision`、`required_database_revision`、`frontend_build_kind`、`frontend_build_sha256` |
| 证据边界 | `evidence_storage_kind`、`raw_evidence_in_git=false`、`limitations` |
| 判定解释 | `lock_reasons` |

`gate7-research-environment-v1` 的 `frontend_build_sha256` 专指参与者实际使用的用户 H5 artifact。OM1 管理端尚未实现；后续 admin-web 的 artifact hash 和镜像 digest 先进入部署发布记录。若研究要求把管理端构建也纳入环境身份，必须创建 manifest Schema v2 并同步 validator、example 和测试，不能在 v1 中静默增加字段或偷换 `frontend_build_sha256` 含义。任何管理操作导致 published snapshot 改变时，仍必须生成新的数据 hash 和 study environment ID。

Manifest 不能包含 API Key、数据库/Redis 密码、完整连接串、私钥、token、`.env` 内容、参与者联系方式、原始录音或精确私人行程。

## 3. 状态判定

状态由工具根据事实推导，操作者不能直接指定：

| 状态 | 含义 | 是否可收集真实 Gate 7 证据 |
|---|---|---|
| `locked` | Git 干净、迁移一致、生产前端产物存在，正式研究使用 published 数据 | 可以，仍须满足招募、知情同意和主持流程 |
| `candidate` | 环境安全但有可修复缺口，如工作树脏、迁移不一致或缺构建产物 | 不可以；只可准备或 dry run |
| `invalid` | 正式研究使用 candidate/synthetic 数据等口径错误 | 不可以 |

当前 reviewed protocol 的 canonical SHA-256 固定为：

```text
b791f0558dfc93af4cc919ec6dd9b09d1251f8f1d54b7bc0bb8809eade742d89
```

协议文件发生任何语义漂移后，锁定工具都会失败。若确需修订 protocol，必须先完成评审、升级版本和哈希，再开始新的证据收集批次；不能在看到研究结果后静默修改。

## 4. 正式锁定步骤

### 4.1 前置门禁

1. 将计划用于研究的应用代码提交，确认 `git status --short` 为空；
2. 使用锁文件安装前端依赖并生成正式 H5 构建：

```powershell
Set-Location frontend
npm ci
npm run build:h5
Set-Location ..
```

3. 在实际研究数据库执行并核对当前代码要求的 Alembic revision。当前要求为 `0006_place_catalog`；
4. 使用通过 R0.2 覆盖、来源、人工审核和 OD 扩容门禁的不可变 published research snapshot；现有 `hangzhou-published-2026-08-27-v1` 只有 7 个路线点，只用于技术回归，不作为 G7-R1 充分数据集；
5. 在 `.local/gate7/<study_environment_id>/` 或外部受控研究空间准备原始证据目录。`.local/` 已被 Git 忽略；
6. 不读取或复制 `.env` 内容到 manifest。数据库 revision 只传版本标识，不传数据库 URL。

数据和部署详细前置见 [`gate7-data-deployment-readiness-plan.md`](gate7-data-deployment-readiness-plan.md)。服务器验证报告仍记录为 `0002_anonymous_identity`，而当前应用要求 `0006_place_catalog`。地点目录迁移已在 R0.2-03 实现，但仍须在 R0.3 先备份、再按 0003→0004→0005→0006 顺序部署和验证；本规范和工具不会自行连接服务器或执行迁移。

### 4.2 生成 manifest

```powershell
py -3.12 scripts/lock_gate7_environment.py `
  --study-environment-id m1-hangzhou-formative-01 `
  --study-phase formative `
  --data-snapshot var/published/hangzhou-g7-formative-v1.json `
  --database-revision 0006_place_catalog `
  --frontend-build frontend/dist `
  --frontend-build-kind h5-production `
  --evidence-storage-kind controlled_local `
  --limitation "Moderated M1 Hangzhou formative study; not a public production release." `
  --output .local/gate7/m1-hangzhou-formative-01/environment.json `
  --require-locked
```

`--require-locked` 在状态不是 `locked` 时返回非零退出码。正式锁定 manifest 若写在仓库内部，输出路径必须被 Git 忽略；这是为了避免“检查时干净、写入 manifest 后立刻变脏”的自相矛盾。仓库中的 [`gate7-research-environment.example.json`](gate7-research-environment.example.json) 只是 synthetic schema 示例，不是正式锁。

## 5. 证据绑定与报告

每份 `gate7-evidence-v1` 的 `environment` 必须包含：

```json
{
  "study_environment_id": "m1-hangzhou-formative-01",
  "environment_manifest_sha256": "<lock command output>",
  "app_version": "0.1.0",
  "result_schema_version": "trip-result-v2",
  "solver_version": "solver-p1-v2",
  "constraint_version": "constraints-p1-v5",
  "parameter_version": "parameters-p1-2026-08-26",
  "data_snapshot_version": "hangzhou-g7-formative-v1"
}
```

生成聚合报告时必须同时提供 manifest：

```powershell
py -3.12 scripts/run_gate7_report.py `
  --protocol docs/test/gate7-protocol-v1.json `
  --environment-manifest .local/gate7/<study_environment_id>/environment.json `
  --evidence .local/gate7/<study_id>/evidence.json `
  --output docs/test/reports/gate7-<study_id>-aggregate.json
```

机器门禁会核对：

- environment ID 与 manifest canonical SHA-256；
- evidence 的应用、结果、solver、constraint、parameter、数据版本；
- manifest 在证据收集开始时间之前生成；
- 真实证据只能引用 `locked` 环境；
- evidence 的研究阶段必须与 manifest 一致；
- synthetic evidence 可以用于 dry run，但不能形成 H3 支持结论。

## 6. 批次变更规则

以下任一变化必须停止当前批次、生成新的环境 ID 和 manifest，并在报告中解释：

- Git commit 或前端构建内容变化；
- published 数据快照变化；
- solver、constraint、parameter 或结果 Schema 变化；
- 数据库 revision 变化；
- protocol 或主持脚本发生影响指标口径的变化；
- blocker/major 修复后进入新一轮回归或招募。

同一个参与者在修复前后的两次结果不能当作两个独立样本。旧 manifest、旧 evidence 和旧聚合报告保持不可变，不覆盖、不回填。

## 7. 当前执行结果

本轮已实际运行 candidate 检查，工具正确识别三个未关闭条件：

```text
dirty_git_tree
database_revision_mismatch
frontend_artifact_missing
```

这是预期结果：锁定工具已由提交 `8bbca5b` 固化，但服务器报告仍是 0002，且前端正式 artifact 和充分研究数据均未形成。2026-08-29 进一步确认当前 7 点数据不足，因此先执行 R0.2 地点数据和 OD 扩容，再执行 R0.3 正式构建/服务器迁移和 R0.4 dry run；三段全部通过后才生成首个 `locked` 形成性研究环境。

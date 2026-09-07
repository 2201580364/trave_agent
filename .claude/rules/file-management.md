# 文件管理纪律（写入位置与层级划分）

**适用**：任何涉及「写规则、写文档、写代码、写脚本、写产物」的任务。目的：新会话开场即知道「什么内容写到哪」，避免规则/文档错位造成管理混乱。本纪律由 2026-09-07 规则落位事故（把细则堆进 AGENTS.md）确立。

## 一、开场强制动作（每次新会话）

1. 已注入 AGENTS.md 的会话：先读 [.claude/rules/](./) 目录清单——至少扫一遍各 rules 文件的标题行，确认本次任务涉及的纪律已加载（尤其 `git-safety.md`、本文件）。
2. 未注入 AGENTS.md 的会话：先读 [AGENTS.md](../../AGENTS.md) → [docs/process/CURRENT.md](../../docs/process/CURRENT.md) → 本文件。
3. 写任何文件前先回答：「这个内容属于哪一层？」——对照下表，答不出来就先问用户，不落盘。

## 二、写入位置对照表（唯一权威）

| 内容类型 | 写到哪 | 不写到哪 |
|---|---|---|
| 一行级硬规则（关键约定） | [AGENTS.md](../../AGENTS.md)「关键约定」+ 链接到对应 rules | 规则正文不堆进 AGENTS.md |
| 完整操作规范/纪律 | `.claude/rules/<主题>.md`（如 git-safety、script-contract） | 不写进 AGENTS.md 或 docs/ |
| 当前节点/基线/下一步/风险 | [docs/process/CURRENT.md](../../docs/process/CURRENT.md)（≤150 行） | 不写进 AGENTS.md、README、CLAUDE.md |
| 历史轮次记录 | [docs/process/status-archive/](../../docs/process/status-archive/) 按月切片（只追加） | 不写进 CURRENT.md（CURRENT 只留最近三轮） |
| 阶段状态表 | [docs/process/transformation-plan.md](../../docs/process/transformation-plan.md) | 不在 CURRENT.md 重复状态表 |
| 设计意图/规格/ADR | docs/product/、docs/domain/、docs/specs/、docs/decisions/ | 「现状」表述只允许出现在 CURRENT.md |
| 机器再生产物 | `var/reports/`（gitignored） | 不放 docs/ |
| 测试代码 | tests/（Python）、admin-web/frontend 内 `*.test.ts` | 不与源码混放 |
| 会话记忆 | `.workbuddy/memory/`（项目级）、`~/.workbuddy/MEMORY.md`（用户级） | 不写进 docs/ 或仓库其他位置 |

## 三、AGENTS.md 与 .claude/rules 的分工细则

- **AGENTS.md**：每次会话强制注入，token 预算敏感。只放「一条能读懂的硬规则 + 指向 rules 的链接」，单条不超过两行；正文超过 5 行的规则一律下沉到 rules。
- **.claude/rules/**：按主题一文件（git-safety、script-contract、solver、data-quality、llm-boundary、decisions-traceability）。新纪律 = 新文件，不往现有文件里无限追加；文件内引用 ADR 必须真实存在（check_docs 会拦截）。
- **CLAUDE.md**：纯薄指针，由 `scripts/sync_agents_docs.py` 从 AGENTS.md 派生，永不手改。
- 修改 AGENTS.md 后必须跑 `python scripts/sync_agents_docs.py`；完成后跑 `python scripts/check_docs.py` 确认门禁全过。

## 四、自查清单（写完文件后过一遍）

1. 内容类型对照第二节表格，位置对了吗？
2. 同一事实是否只在一处维护（唯一权威位置），没有在两处复述？
3. AGENTS.md 是否仍 ≤100 行、CURRENT.md 是否仍 ≤150 行？
4. 新建的 rules 文件是否已加入「任务类型 → 阅读路由表」（如适用）？
5. sync + check_docs 跑过了吗？

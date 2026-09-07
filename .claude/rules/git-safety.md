# Git 与文件操作安全规则

**适用**：任何会话中的 git 操作与文件系统破坏性操作。本规则由用户于 2026-09-07 明确要求（背景：.git 损坏事故），优先级高于任何任务指令。

## 一、Git 操作分级

1. **AI 允许（只读）**：`git status` / `log` / `diff` / `show` / `branch` / `remote -v` 等只读命令。
2. **AI 允许（工作区编辑）**：使用文件工具编辑、新建、修改工作区文件；`git add` 暂存属于边界灰区，默认也不做，改动清单直接交给用户。
3. **AI 禁止自动执行（用户手动）**：
   - `git commit`、`git push`
   - `git merge`、`git rebase`、`git cherry-pick`
   - 分支的创建/切换/删除（`checkout -b`/`branch -d`）
   - 一切 force/discard 类：`checkout -f`、`reset --hard`、`clean`、`stash drop`
4. 需要提交时，AI 准备好改动文件清单与建议的 commit message，明确告知用户手动执行。

## 二、文件删除纪律

1. **删除任何文件/目录前，必须先向用户列出完整清单（逐个路径）并获得显式确认**；确认前只做扫描报告，不动文件。
2. `rm` / `rm -rf` / `Remove-Item` / `rmdir` / 批量删除 / 清空目录一律禁止自动执行。
3. **`.git` 目录本身永不删除或重建**。发现 git 异常（refs 丢失、对象损坏、bad object）时：停止一切 git 操作，报告现象，由用户决定恢复方式（如从远端重新 clone 应由用户执行或显式确认后执行）。
4. 个人目录（Desktop/Downloads/Documents 等非项目目录）的整理、清理请求，一律先扫描出报告再等用户逐项确认。

## 三、测试与脚本副作用

1. 测试运行（pytest/vitest/typecheck/build）不得产生删除副作用；若某测试或脚本需要写入/删除文件（如 fixture 清理、报告轮转），运行前先向用户说明其副作用。
2. scripts/ 工具面遵循 `.claude/rules/script-contract.md` 的三级分类：未登记的写入类脚本默认按 L2 处理（dry-run + 显式确认），破坏类（L3）永不自动执行。

## 四、违规处理

任何一次违反本规则的操作（即使"结果没坏"）都应立即向用户报告并记录到会话产出中；不允許以「抢救」「紧急」为由绕过确认流程。

# trave_agent

旅行助手：输入目的地，自动规划旅行路线，搞定衣食住行。

当前处于 `M1 — 行程骨架验证`。当前执行节点、测试基线与下一步统一见 [docs/process/CURRENT.md](docs/process/CURRENT.md)（不在本文件复述，避免状态漂移）；跨里程碑稳定路线见 [docs/process/project-roadmap.md](docs/process/project-roadmap.md)。

## 目录导航

| 路径 | 用途 |
|---|---|
| `src/travel_agent/` | 后端领域、应用、基础设施、HTTP 与求解器实现 |
| `frontend/`、`admin-web/` | 用户端与管理端源码、测试和构建配置 |
| `tests/`、`migrations/`、`scripts/` | 后端测试、数据库迁移、维护工具 |
| `data/`、`spike/` | 受版本管理的数据规范/候选资料、历史技术验证材料 |
| `deploy/production/` | Dockerfile、Compose 和部署配置；仅本地构建应用镜像 |
| `docs/`、`.claude/` | 规格、状态账本、项目工作规则与技能 |
| `.local/` | 本机数据库、凭证与验证环境，不进入版本控制 |
| `var/reports/`、`var/cache/` | 可再生报告、pytest/mypy/ruff 等工具缓存 |
| `logs/` | 运行日志，不进入版本控制 |

目录整理不通过移动业务模块来改变导入路径。历史数据库、备份与验证材料须核对用途后再处理；文件位置纪律见 [.claude/rules/file-management.md](.claude/rules/file-management.md)。镜像发布流程见 [.claude/skills/docker-image-deploy/SKILL.md](.claude/skills/docker-image-deploy/SKILL.md)。

## 本地运行

后端要求 Python 3.12：

```text
py -3.12 scripts/run_local_dev.py
```

启动脚本默认读取 `.env` 中的 `TRAVEL_AGENT_DATABASE_URL`；需要临时覆盖 SQLite 文件时可使用 `--database .local/xxx.db`。当前本地人工核验环境使用 `.local/research.db`。

前端要求 Node.js 22 和 npm 10：

```text
cd frontend
npm ci
npm run dev:h5
```

然后访问 `http://127.0.0.1:10086`。本地数据库位于 `.local/`，运行日志遵循 `logs/<module>/<level>/YYYY-MM-DD.log`；两者均不会提交到 Git。

项目当前状态见 `docs/process/CURRENT.md`；管理侧路线和功能见 `docs/product/管理端功能模块设计.md`；历史轮次记录见 `docs/process/status-archive/`。

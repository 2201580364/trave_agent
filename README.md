# trave_agent

旅行助手：输入目的地，自动规划旅行路线，搞定衣食住行。

当前处于 `M1 — 行程骨架验证`。当前执行节点、测试基线与下一步统一见 [docs/process/CURRENT.md](docs/process/CURRENT.md)（不在本文件复述，避免状态漂移）；跨里程碑稳定路线见 [docs/process/project-roadmap.md](docs/process/project-roadmap.md)。

## 本地纵向切片

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

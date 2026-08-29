# trave_agent

旅行助手：输入目的地，自动规划旅行路线，搞定衣食住行。

当前处于 `M1 — 行程骨架验证 / Gate 7 R0.2-05-01B O00/O16 管理 Web 壳与安全操作面`。R0.2-04 已形成 72 个杭州 candidate、11 区域/9 类别覆盖矩阵和 11 组未裁决关系线索；它们尚未 human_verified，也未进入求解器。求解器核心已阶段性完成；OM1 独立管理身份、API/RBAC、管理员角色和结构化审计后端底座及 Alembic 0007 已实现，当前建设与 Taro 用户端分离的管理 Web。

## 本地纵向切片

后端要求 Python 3.12：

```text
py -3.12 scripts/run_local_dev.py
```

前端要求 Node.js 22 和 npm 10：

```text
cd frontend
npm ci
npm run dev:h5
```

然后访问 `http://127.0.0.1:10086`。本地数据库位于 `.local/`，运行日志遵循 `logs/<module>/<level>/YYYY-MM-DD.log`；两者均不会提交到 Git。

项目整体状态和续接入口见 `docs/process/project-status.md`；管理侧路线和功能见 `docs/product/管理端功能模块设计.md`。

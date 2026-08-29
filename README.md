# trave_agent

旅行助手：输入目的地，自动规划旅行路线，搞定衣食住行。

当前处于 `M1 — 行程骨架验证 / Gate 7 R0.2-05-01 OM1 管理身份、管理 API 与审计底座`。R0.2-04 已形成 72 个杭州 candidate、11 区域/9 类别覆盖矩阵和 11 组未裁决关系线索；它们尚未 human_verified，也未进入求解器。求解器核心已阶段性完成，首个匿名浏览器纵向切片采用 FastAPI + SQLAlchemy + Taro/React；管理侧 OM1 产品设计已完成，当前开始实现独立管理身份、API/RBAC 和业务审计底座。

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

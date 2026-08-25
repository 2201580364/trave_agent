# Travel Agent Frontend

Taro 4 + React 的 M1 移动端优先前端，首个纵向切片包含：

```text
P00 首页
→ P01 什么时候去
→ P02 想去哪里
→ P03 确认并生成
→ P04 行程详情
```

## 运行环境

当前可重复验证基线：

```text
Node.js 22.23.2
npm 10.9.8
```

项目通过 `package.json#engines`、`packageManager` 和 `.nvmrc` 固定 Node 22 主版本。Node 24 不作为当前支持环境，因为 Taro 4.2.1 的 SWC 与 npm 可选原生依赖在 Windows 上存在兼容性问题。

## 本地命令

```text
npm ci
npm run typecheck
npm run dev:h5
npm run build:h5
```

H5 开发服务器默认运行在 `http://127.0.0.1:10086`，并将 `/api`、`/health` 代理到 `http://127.0.0.1:8000`。

前端只展示服务端返回的排程、未排入、降级和质量信息，不在页面中重新计算 C1–C6，也不重新排列行程节点。

## 本地后端

从仓库根目录运行：

```text
py -3.12 scripts/run_local_dev.py
```

该命令会升级 `.local/travel_agent.db` 的 Alembic 迁移，并启动真实 FastAPI、SQLAlchemy 与 ProductionSolverGateway 组合。景点、天气和 OD 数据是明确标注的本地杭州验证快照，不代表生产发布数据。

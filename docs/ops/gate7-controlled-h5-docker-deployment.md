# Gate 7 受控 H5 全容器部署方案

- 文档版本：V1.1
- 日期：2026-08-29
- 产品里程碑：M1 — 行程骨架验证
- 所属阶段：G7-R0.3
- 当前状态：用户 H5 与 OM1 管理端部署边界已确定，Compose 应用层尚未实现
- 部署约束：所有应用与依赖服务统一使用 Docker 镜像，由 Docker Compose 管理

## 1. 部署结论

G7-R1 的受控测试入口采用移动端 H5。服务器宿主机不直接安装或以 systemd 运行 FastAPI、Node.js、Nginx/Caddy、MySQL、Redis；除 Docker Engine、Docker Compose、必要的宿主机安全配置和备份调度外，运行组件全部容器化。

现有 `deploy/production/docker-compose.yml` 只包含 MySQL/Redis。R0.3 实施时扩展为一个逻辑 Compose 项目：

```text
name: travel-agent

edge       HTTPS、用户 H5、管理端静态文件、/api 与 /health 反向代理
admin-web  OM1 桌面管理端构建产物；可由 edge 挂载或独立静态容器提供
api        FastAPI/Uvicorn 生产组合根
migrate    与 api 同镜像的一次性 Alembic 迁移任务
mysql      MySQL 8.0 持久化数据库
redis      Redis 7.4 ACL、缓存和 Provider 治理状态
backup     可选 tools profile，一次性备份/校验任务
```

禁止把应用容器另行用 `docker run`、宿主机 Python 虚拟环境或 PM2 管理，否则研究环境无法由单一 manifest 回放。

## 2. 目标拓扑

```text
外部受邀参与者
        │
        │ HTTPS 443
        ▼
┌──────────────────────┐
│ edge                  │
│ Caddy + UI artifacts  │
│ /       → user H5     │
│ /admin/ → admin-web   │
│ /api/*  → api:8000    │
│ /health → api:8000    │
└──────────┬───────────┘
           │ frontend network
           ▼
┌──────────────────────┐
│ api                   │
│ FastAPI/Uvicorn       │
│ file logs, no console │
└───────┬────────┬─────┘
        │ backend network
        ▼        ▼
┌────────────┐ ┌────────────┐
│ mysql      │ │ redis      │
│ internal   │ │ internal   │
└────────────┘ └────────────┘
```

网络规则：

- `edge` 只加入 `frontend` 网络；
- `api` 同时加入 `frontend` 和 `backend`；
- `mysql`、`redis` 只加入 `backend`；
- 公网只开放 edge 的 80/443；
- `/admin/` 与 `/api/v1/admin/*` 使用独立管理员认证；初期受控环境可叠加邀请访问或 IP allowlist，但网络隐藏不能替代服务端 RBAC；
- API 8000 不映射公网端口；
- MySQL/Redis 不开放公网端口；
- 运维确需宿主机验证时，只允许保留已有 `127.0.0.1:13306/16379` 回环绑定，应用容器始终使用 `mysql:3306`、`redis:6379` 服务名。

## 3. 镜像与构建

### 3.1 API 镜像

计划新增：

```text
deploy/production/api.Dockerfile
```

要求：

- 基于固定 Python 3.12 小版本镜像；
- 使用非 root 用户运行；
- 安装 `pyproject.toml` 中的正式依赖，不安装 dev 依赖；
- 复制 `src/`、`migrations/`、`alembic.ini` 和必要启动入口；
- 不复制 `.env`、`.local/`、`var/cache/`、私钥或测试原始证据；
- 默认启动 `scripts/run_published_app.py --host 0.0.0.0 --port 8000` 或等价模块入口；
- 关闭 Uvicorn access log，业务日志写入受控文件卷；
- 镜像标签包含 Git commit，不使用不可追踪的 `latest` 作为研究锁依据。

### 3.2 Edge、用户 H5 与管理端镜像

计划新增：

```text
deploy/production/web.Dockerfile
deploy/production/admin-web.Dockerfile
deploy/production/Caddyfile
```

采用多阶段构建：

```text
Node 22 + npm ci + npm run build:h5
→ 只复制 frontend/dist 到用户 H5/Caddy 运行镜像

Node 22 + npm ci + npm run build（OM1 实现后）
→ 只复制 admin-web/dist 到管理端静态镜像或 edge 管理目录
```

要求：

- Node/npm 版本沿用 `.nvmrc`、`engines` 和 package-lock；
- 运行镜像不包含 node_modules、源代码或开发服务器；
- SPA 路由回退到 `index.html`；
- `/api/*` 和 `/health` 反向代理到 `api:8000`；
- 开启压缩、静态资源缓存和基础安全响应头；
- 研究环境使用受控域名和可信 HTTPS；
- H5 artifact 目录 SHA-256 和最终镜像 digest 都进入研究环境记录。
- admin-web 使用独立构建目录/hash，不能和用户 H5 共用会话配置或把管理 DTO 打入用户 bundle；
- 高德 Web 服务 Key、MySQL/Redis 凭证不进入任何前端镜像。管理地图如使用浏览器 SDK，必须使用独立受域名/用途限制的浏览器端凭证，并与服务端 Web 服务 Key 分离；

### 3.3 迁移任务

`migrate` 使用与 `api` 完全相同的镜像，但不常驻：

```powershell
docker compose run --rm migrate
```

规则：

- 数据库迁移在 `api` 更新前显式执行；
- 迁移容器临时使用服务器权限受限的 migration env；
- API 容器只获得 DML 应用账号；
- 迁移失败时不启动新 API；
- 不自动执行 downgrade；
- 回滚应用前必须检查数据库向后兼容性，而不是仅切换镜像标签。

## 4. Compose 文件组织

保持一个权威 Compose 项目，避免基础设施与应用分别漂移。建议结构：

```text
deploy/production/
├── docker-compose.yml          # edge/user-h5/admin-web/api/migrate/mysql/redis/backup
├── api.Dockerfile
├── web.Dockerfile
├── admin-web.Dockerfile
├── Caddyfile
├── infra.env.example
├── app.env.example             # 仅变量名和占位值
├── mysql/
├── redis/
├── scripts/
├── validation/
└── README.md
```

可以使用 Compose profile 控制一次性工具：

```text
default profile  edge/user-h5/admin-web/api/mysql/redis
tools profile    migrate/backup/restore validation
```

但所有 profile 仍属于同一个 `name: travel-agent` 项目和同一份版本化 Compose 配置。

## 5. 配置与秘密

服务器继续使用：

```text
/etc/travel-agent/infra.env     root:root 0600
/etc/travel-agent/app.env       root:root 0600
/etc/travel-agent/migrate.env   root:root 0600，迁移时临时挂载
```

规则：

- 真实值不进入 Git、镜像层、Compose 文件、构建参数或研究 manifest；
- `app.env` 只包含应用 MySQL DML URL、Redis ACL URL、Provider 设置、发布数据路径和分享密钥；
- `migrate.env` 不注入常驻 API；
- 高德/和风服务端 Key 只进入 API/数据构建任务需要的环境，不进入 edge、user-h5 或 admin-web；
- 容器日志、`docker inspect` 输出和健康检查不得回显密码或完整连接串；
- 不使用 Compose 命令行 `-e PASSWORD=...`，避免进入 shell history。

## 6. 持久化目录

```text
/srv/travel-agent/data/mysql/        MySQL
/srv/travel-agent/data/redis/        Redis AOF/RDB
/srv/travel-agent/data/published/    immutable published research snapshots
/srv/travel-agent/logs/api/          应用 debug/info/error 日志
/srv/travel-agent/logs/edge/         边缘访问/错误日志
/srv/travel-agent/backups/mysql/     MySQL 备份
/srv/travel-agent/backups/redis/     Redis 备份
/srv/travel-agent/research/gate7/    受控原始研究材料，不进入应用镜像
```

API 将 `/srv/travel-agent/logs` 和 published 数据目录分别以可写/只读方式挂载。原始研究材料不挂载进普通 API/edge/user-h5/admin-web 容器，只有经过授权的研究处理任务可以访问。管理业务审计写入 MySQL，不依赖文件日志卷作为唯一证据。

## 7. 日志规则

应用业务日志继续沿用现有要求：

```text
logs/api/debug/YYYY-MM-DD.log
logs/api/info/YYYY-MM-DD.log
logs/api/error/YYYY-MM-DD.log
```

- 不按容器实例拆目录；
- 每日新文件；
- 每月压缩归档；
- API `enable_console=false`，不把全部业务日志一股脑写到 stdout；
- Docker `json-file` 只保留容器启动、崩溃和极少量运行时输出，并设置 `max-size/max-file`；
- edge 访问日志与 API 业务日志分开；
- token、API Key、完整 URL、私人交通和研究身份不进入日志。

## 8. 健康检查和启动依赖

最低健康检查：

| 服务 | 健康检查 |
|---|---|
| mysql | 容器内 socket `SELECT 1` |
| redis | ACL 用户 `PING` |
| api | `/health/ready`，校验 DB revision、published snapshot 和依赖状态 |
| edge | 本地请求用户首页、受保护管理入口和 `/health` 代理 |
| admin-web | 静态 artifact 可读取；管理 API 未认证请求被拒绝 |

启动顺序不只依赖 `depends_on`：

```text
mysql/redis healthy
→ backup
→ migrate success
→ api ready
→ edge ready
→ Chrome/HTTP 验收
→ environment manifest locked
```

## 9. 发布流程

```text
1. 固定 clean Git commit
2. 构建 api/edge/user-h5/admin-web 镜像
3. 记录镜像 digest、用户 H5 artifact hash 和 admin-web artifact hash
4. docker compose config 门禁
5. 服务器数据库/Redis 备份
6. docker compose run --rm migrate
7. docker compose up -d mysql redis api user-h5 admin-web edge
8. 等待全部 healthy
9. 执行持久化、身份隔离、分享/反馈和数据版本验收
10. 真实 Google Chrome 移动端/桌面端回放
11. 备份恢复演练
12. 生成 locked Gate 7 environment manifest
13. 执行 R0.4 internal dry run
```

不允许在参与者 session 中执行 `docker compose build`、迁移、切换数据版本或滚动修改环境。修复 blocker/major 后生成新镜像、重新部署并创建新的 environment ID。

## 10. 回滚和恢复

- API/edge/user-h5/admin-web 镜像保留至少当前和上一研究批次 digest；
- published snapshot 不覆盖，只切换版本指针；
- MySQL 迁移前必须完成可校验备份；
- 数据库 schema 变化优先采用向后兼容 expand/contract；
- 迁移后若旧镜像不兼容，不能只执行 `docker compose up` 回滚；
- Redis 可以从 RDB/AOF 恢复，但不能作为唯一业务事实来源；
- 恢复演练使用隔离容器/Volume，不覆盖当前研究环境。

## 11. G7-R0.3 退出条件

- 所有常驻组件均由一个 Docker Compose 项目管理；
- `docker compose config`、镜像构建、健康检查和资源限制通过；
- 公网只暴露 80/443；
- API、MySQL、Redis 不直接暴露公网；
- 数据库达到研究构建要求 revision；
- published research snapshot 可加载并通过 hash 校验；
- API 日志按模块/级别/日期落盘并可月度归档；
- 用户 H5 从受控 HTTPS 地址可访问；管理端使用独立登录和权限，普通用户不能访问候选/审核数据；
- 身份隔离、Revision、分享和反馈通过；
- Chrome 移动端/桌面端及受控失败恢复通过；
- 镜像 digest、artifact hash 和 Compose 版本进入 locked manifest；
- R0.4 开始后环境不再临时修改。

## 12. 当前实施边界

本文件只确定部署方式。当前尚未新增 API/user-h5/admin-web Dockerfile，也未扩展现有 Compose；服务器上的 MySQL/Redis 继续按已验收的 `travel-agent-infra` 项目运行。OM1 管理端、后续迁移和 R0.2 published research snapshot 未完成前，不提前重建服务器应用栈，避免短期内连续迁移和重复发布。

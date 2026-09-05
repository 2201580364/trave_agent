# ADR-0020：admin-web 独立管理前端工程与技术栈

状态：已接受（M1 / OM1 / R0.2-05-01B）

## 背景

OM1 需要一个供数据编辑员、审核员、发布者和管理员使用的管理操作面。用户端是 Taro 4（H5 + 微信小程序目标），但管理端是纯桌面 Web 工作台：不需要跨端能力、不需要进入 Taro 用户包，且对表格、表单、筛选和审计展示有较高密度要求。若把管理页面塞入 Taro 工程，会把管理依赖打进用户包，并让两套差异极大的交互模式互相牵制。

## 决策

- 管理前端作为独立 `admin-web/` 工程，与 `frontend/`（Taro 用户端）完全分离；依赖与构建产物不进入 Taro 用户包。
- 技术栈：React 19 + TypeScript + Vite + React Router + Ant Design；测试用 Vitest + Testing Library（含 `@testing-library/jest-dom`）。
- 与后端通过独立 `/api/v1/admin` 管理域 API 通信；本地开发由 Vite 将 `/api` 与 `/health` 代理到 `127.0.0.1:8000`。
- 安全边界：Bearer token 仅保存在 React 进程内存，不写入 `localStorage`、`sessionStorage`、Cookie、URL、日志或错误文本；页面刷新后必须重新登录。前端权限只用于改善交互，授权事实来源始终是服务端 RBAC。
- 管理端不能直连 MySQL，也不能通过通用 PATCH/SQL 写 published；发布只能走共享 application/domain 发布用例（见 ADR-0019）。

## 取舍

- 选择 Ant Design 而非轻量自研组件：管理端信息密度高、生命周期长，成熟表格/表单体系的收益大于包体成本。
- 选择「内存 token + 刷新重登」而非持久会话：牺牲管理操作连续性，换取会话泄露面最小化；后续如引入会话持久化，必须新立 ADR 并补安全评审。
- 不复用 Taro：避免跨端约束污染桌面工作台设计。

## 验收条件

- `npm run typecheck`、`npm run test`（Vitest）、`npm run build` 全部通过。
- 用户端构建产物中不包含 admin-web 依赖。
- 401/会话过期时清空内存主体并回到登录页。

# 问题清单收口验证报告（2026-09-16）

本轮目标是收口 `var/reports/admin-issue-ledger-20260915.json` 中剩余问题，并对新发现的投影、O17 权限与页面验证问题补回归。

## 已解决项

- `TYPE-001`：全仓 strict mypy 清零，锁定环境输出 `Success: no issues found in 242 source files`。
- `OD-QUALITY-001`：本地近似 OD 不再按短耗时推断为步行；只有显式 `ODTravelMode.WALKING` 才展示步行，未知近似短边展示为打车估算。
- `DATA-PLACE-002`：浙江省博物馆孤山馆区当前 published v4 为 `indoor_outdoor=indoor`，published projection `is_indoor=true`；内置 Chrome 选点页显示“室内 · 建议70分钟”。
- `ADMIN-DATA-001`：平湖秋月按用户确认保留名称与 40 分钟建议时长；通过应用接口发布 v4，published projection `solver_projection_f46fb0c9da824b2bae7de03c3a65e582`，`data_verified=true`，`solver_node_id=25`。
- `ADMIN-O17-001`：O17 读/写权限拒绝均带 `required_permission`，无权限账号返回 403，不再触发 500。
- `PROJECTION-DATA-001`：投影准备 gate 通过后持久化的 `solver_payload.data_verified` 为 `true`，并新增 HTTP 回归。
- `PROJECTION-REL-001`：关系来源允许属于关系任一端；准备投影与发布门禁使用一致上下文，父地点来源不会误判为当前地点来源冲突。

## 本地浏览器验证

环境：本地 API 8000/8001、管理端 5173、用户端 H5 10086，数据库 `.local/research.db`。API 在平湖秋月 v4 发布后重启，以清除发布目录进程缓存。

内置 Chrome 用户端全流程：

1. 首页新建行程。
2. 日期保持 2026-09-30 至 2026-10-02，09:00 开始，末日 18:00 结束。
3. 选择 10 个景点：灵隐寺、飞来峰景区、西溪国家湿地公园、断桥残雪、浙江省博物馆孤山馆区、平湖秋月、清河坊历史文化特色街区、钱江新城灯光秀、武林夜市、杭州运河游船。
4. 生成行程后页面显示 3 天、10 已安排、0 未排入。
5. 刷新行程详情页后仍恢复 3 天、10 已安排、0 未排入。

页面可见数据核对：

- 平湖秋月：室外，体力 2 星，建议 40 分钟，全天开放信息已验证。
- 浙江省博物馆孤山馆区：室内，体力 3 星，建议 70 分钟，每周闭馆 1。
- 灵隐寺与飞来峰景区同日安排，上一站到飞来峰显示步行 50 米、约 5–10 分钟。

最终一次页面结果仍观察到平湖秋月与断桥残雪分天：平湖秋月在第 1 天，断桥残雪在第 3 天。该结果没有违反 C1/C2/C4/C5/C6，也没有漏排；已登记为 `SOLVER-QUALITY-004`，后续应作为邻近体验偏好/目标函数优化继续处理。

## 自动验证

- `python -m pytest -q`：全量通过（本轮代码修复后跑通；随后新增的 projection payload 断言又做了专项复跑）。
- `python -m pytest tests/golden -q`：9/9 通过。
- `python -m ruff check src tests scripts`：通过。
- `python -m mypy`：通过，242 个源文件无错误。
- `python scripts/check_layering.py`：153 文件，0 违规。
- `python scripts/check_docs.py`：通过。
- 追加专项：投影准备、关系来源、O17 403、C6 近似 OD、solver gateway 旧断言修正均通过。


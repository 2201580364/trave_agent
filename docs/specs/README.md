# 需求规格（Specs）

> 需求规格 = 功能 + **Given/When/Then 验收标准** + 可追溯的假设编号。
> 由 `/spec` 命令或 `spec` skill 从产品文档生成，G2 阶段产出。

## 文件约定

- 每个功能一篇，命名 `xxx.md`（如 `trip-solver.md`）。
- 头标含：关联假设（`H-x`）、关联指标、优先级。

## 验收标准模板

```
### 功能：一键生成分日行程（关联 H3、H7）

场景：用户选定 5 个景点、3 天、正常模式、周一到达
Given 某景点 close_day=1（周一闭馆）
When 求解器生成 Day 1（周一）行程
Then 该景点不出现在 Day 1
```

## 待写的核心规格（按优先级）

1. `trip-solver.md` —— 一键生成分日行程（核心，承载 H3，最优先）
2. `attraction-browse.md` —— 景点列表 + 类型筛选
3. `transport-input.md` —— 大交通输入（关联 H6）
4. `replace-regenerate.md` —— 替换景点 + 重新生成
5. `share-card.md` —— 行程分享卡片（关联 H11）
6. `feedback.md` —— 👍👎 反馈

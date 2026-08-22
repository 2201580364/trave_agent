---
name: data-validate
description: 在采集、转换、导入或修改景点 POI 硬事实数据时使用；校验 P1 多套时间窗、闭馆规则、来源、冲突与 data_verified 门禁。
---

# 数据校验技能

> 求解器的正确性 100% 依赖数据准确。数据错则「硬约束 100%」是假指标。

## 校验清单

以 [开放时间数据规范](../../../docs/domain/开放时间数据规范.md) 和 [P1 数据模型](../../../docs/specs/data-model.md) 为准：

1. `time_rules` 每项包含有效日期区间、`open`、`close` 和可空 `last_entry`。
2. `close > open`；跨午夜规则用结束时间 `+1440` 表示并显式标记。
3. `last_entry ≤ close`；日期区间不得无意重叠或互相冲突。
4. `close_days` 是不重复的整数数组，元素范围 `1..7`。
5. `is_always_open=1` 时 `time_rules` 可为空；否则至少一条规则匹配目标日期。
6. `suggested_duration > 0`，`energy_level ∈ 1..5`，`category` 属于 9 类枚举。
7. 经纬度在目标城市合理范围内。
8. 硬事实带 `data_source` 和 `fetched_at`；多源冲突设置 `conflict=1` 并人工裁决。
9. `data_verified=1` 且 `conflict=0` 才可进入求解器输入集。

`close_day_exception` 必须保留原始语义和来源；需要节假日判断时由结构化例外规则处理，不让 LLM 在运行时解释决定。

## 流程

1. 每条规则先写校验测试，再写校验函数。
2. 跑全量校验，分别输出格式错误、未校准、过期和冲突清单。
3. P1 的开放时间与闭馆日 100% 人工校准；AI 只辅助抽取候选值。
4. 人工核对来源、时间戳和冲突后才设置 `data_verified=1`。
5. 将过滤函数纳入求解器入口测试，证明未验证或冲突数据不会进入求解。

## 遵守规则

见 [.claude/rules/data-quality.md](../../rules/data-quality.md)。

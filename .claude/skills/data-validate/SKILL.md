---
name: data-validate
description: 景点 POI 数据校验：格式/范围/一致性校验 + 数据质量门禁（source/verified），守住「硬事实」准确
---

# 数据校验技能

> 求解器的正确性 100% 依赖数据准确。数据错则「硬约束 100%」是假指标。

## 校验清单（对照 [docs/domain/开放时间数据规范.md](../../../docs/domain/开放时间数据规范.md)）

1. `close_time > open_time`（跨午夜营业用内部 1440 表示）
2. `close_day` ∈ {0..7}
3. `suggested_duration > 0` 且 ≤ 营业时长
4. `energy_level` ∈ {1..5}
5. `category` ∈ 9 类枚举
6. `lat`/`lng` 在合理范围
7. 每字段有 `data_source`；`data_verified=1` 才可进求解器

## 流程

1. 写校验函数（每个规则一个）。
2. 跑全量校验，输出「未校准」清单。
3. 对未校准数据人工抽检，抽样比例由 Data Quality Spike 结论决定。
4. 抽检通过 → 置 `data_verified=1`。

## 遵守规则

见 [.claude/rules/data-quality.md](../../rules/data-quality.md)。

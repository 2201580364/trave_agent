# 数据模型终稿（M1）

> 落实 ADR-0002：多套时间窗 + 闭馆日例外 + 质量门禁。语义规范见 [../domain/开放时间数据规范.md](../domain/开放时间数据规范.md)。

## 景点表（attractions）—— 核心表，已升级

```sql
CREATE TABLE attractions (
    id INT PRIMARY KEY AUTO_INCREMENT,
    city_id INT NOT NULL,
    name VARCHAR(100) NOT NULL,
    category ENUM('自然山水','古镇人文','寺庙祈福','城市观景','博物馆','美食街区','网红打卡','亲子乐园','演出演艺'),
    energy_level TINYINT NOT NULL,          -- 1-5 体力消耗
    suggested_duration INT NOT NULL,        -- 建议游览分钟
    is_indoor TINYINT DEFAULT 0,            -- 0=室外,1=室内
    lat DECIMAL(10,7), lng DECIMAL(10,7),
    suitable_crowd JSON, best_season JSON, tags JSON,

    -- ★ 多套时间窗（ADR-0002）：按日期区间解析当天时间窗
    --   例: [{date_range:["01-01","03-15"], open:"08:00", close:"17:30", last_entry:"17:00"},
    --        {date_range:["03-16","12-31"], open:"08:00", close:"19:00", last_entry:"18:30"}]
    time_rules JSON NOT NULL,
    is_always_open TINYINT DEFAULT 0,       -- 1=全天开放（西湖等，无固定时间窗）
    close_days JSON,                        -- 闭馆日，如 [1,2]=周一+周二闭馆；[]=无
    close_day_exception VARCHAR(100),       -- 如 "节假日开放"（ADR-0002 例外规则）

    -- 质量门禁（ADR-0002）
    data_source VARCHAR(50) NOT NULL,       -- gaode/baidu_baike/ctrip/manual
    fetched_at DATETIME,                    -- 抓取时间戳（时效性）
    data_verified TINYINT DEFAULT 0,        -- 0=未校准,1=已人工校准
    conflict TINYINT DEFAULT 0,             -- 1=多源冲突待裁决
    status TINYINT DEFAULT 1
);
```

## 关键字段语义

- **`time_rules`**：多个 `{date_range, open, close, last_entry}`。求解器按出行日期匹配区间，解析出当天 `[open_min, close_min, last_entry_min]`。无匹配区间 → 标记数据缺失，不进求解器。
- **`last_entry`（有效入园截止）**：解决「停止售票/停止入园/闭园」多口径问题（ADR-0002 结论 4）。求解器以 `arrival ≤ last_entry` 为硬约束。
- **`is_always_open`**：开放式景点（西湖）标记，跳过时间窗约束。
- **`close_days`**：闭馆日集合（如 `[1,2]` = 周一+周二闭馆，`[]` = 无）。求解器 C1：`weekday ∈ close_days → 不可排`。
- **`close_day_exception`**：闭馆日的例外（如「遇法定节假日顺延」），求解器结合节假日表判断。
- **`data_verified` 门禁**：开放时间/闭馆日字段 `data_verified=1` 才进求解器输入集（ADR-0002 决策 3）。

## 其余表（沿用技术选型文档 5.3，微调）

### 游览时段软偏好

时段偏好不是 `time_rules` 的一部分，也不直接写入景点开放时间字段。策展和公开攻略候选可使用独立数据集或偏好表保存：

```text
attraction_id
preferred_buckets JSON
acceptable_buckets JSON
source ENUM('curated','public_guide_synthesis')
source_ref VARCHAR(...)
version
```

行程请求可携带 `source='user'` 的覆盖项。应用层按 `user > curated > public_guide_synthesis` 解析成单一有效偏好后传给求解器；同级冲突必须人工或上游裁决。该数据只用于软目标，不能修改 `time_rules`、`last_entry` 或 C2 有效窗口。

- **trips**：`itinerary JSON` 存求解器输出；新增 `weather_basis ENUM('forecast','climate')` 标注天气数据来源。
- **feedbacks**：不变。
- **attraction_conflicts**（新增，可选）：多源冲突记录，`conflict=1` 时人工裁决留痕。

## 校验规则

见 [../domain/开放时间数据规范.md](../domain/开放时间数据规范.md) 校验规则 1–7，另加：
8. `time_rules` 每个区间 `close > open` 且 `last_entry ≤ close`。
9. `is_always_open=1` 时 `time_rules` 可为空；否则必须至少一个区间。

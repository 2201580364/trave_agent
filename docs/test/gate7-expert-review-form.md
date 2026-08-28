# Gate 7 领域专家评审表

- 表单版本：G7-EXPERT-V1
- 对应 protocol：`m1-hangzhou-gate7-v1`
- 每份表只评价一个专家、一个场景、一个不可变 TripRevision

## A. 证据标识

```text
review_id:
participant_id:             # 随机假名，不填姓名/联系方式
scenario_id:
trip_id_hash:
revision_id_hash:
app_version:
result_schema_version:
solver_version:
constraint_version:
parameter_version:
data_snapshot_version:
reviewed_at:
source_ref:                 # 受控原始记录引用
```

## B. 独立评分

评分含义：1=不可接受，2=明显问题，3=勉强可用，4=可接受，5=专业可靠。

| 维度 | 1–5 | 必填依据（引用日期/node） |
|---|---:|---|
| 开放、闭馆、最晚入园和固定场次 | | |
| 到达/离开边界和返程安全 | | |
| 同日空间与真实 OD 合理性 | | |
| 上午/下午/晚上分布 | | |
| 午晚餐与连续游览节奏 | | |
| 建议游览时长 | | |
| 体力与同行人群匹配 | | |
| 交通方式与接驳可执行性 | | |
| 未排入/降级解释 | | |
| 总体可交付性 | | |

## C. 强制问题

```text
1. 是否存在硬约束或安全错误？ yes / no
2. 是否存在虚构或误标为真实的地图/天气数据？ yes / no
3. 是否有景点被静默丢失？ yes / no
4. 是否愿意把该计划交付给真实游客？ yes / no
5. 最需要修正的一个 Revision/node：
6. 如果只允许改一个地方，会改什么：
```

任一 1–3 为 yes 时必须创建 blocker issue，不能只降低平均分。

## D. 问题登记

每个问题单独登记：

```text
issue_id:
severity: blocker | major | minor | observation
primary_attribution: data | algorithm | interaction | expectation_management |
                     infrastructure | research_protocol | out_of_scope
secondary_attribution: null | <同枚举>
revision_or_node_ref:
observed_behavior:
expected_behavior:
evidence_source_ref:
suggested_direction:       # 只记方向，不要求专家设计实现
```

## E. 评审者声明

```text
- 我没有参与该 Revision 的设计、生成或历史评分：yes / no
- 我在提交前没有看到其他专家的结论：yes / no
- 我没有把个人偏好误写成硬约束：yes / no
```


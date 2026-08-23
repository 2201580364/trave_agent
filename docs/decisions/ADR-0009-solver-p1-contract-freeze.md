# ADR-0009：P1 求解器契约冻结

- **状态**：已接受
- **日期**：2026-08-24
- **决策者**：产品 + 工程
- **关联假设**：H3、H7
- **前置**：ADR-0003、ADR-0004、ADR-0005、ADR-0006、ADR-0007、ADR-0008

## 背景

求解器已经完成 C1/C2/C4/C5/C6、分天、日内路由、晚间分段、晚餐降级、跨天恢复、搜索状态、审计、接近度和游览时段软偏好。如果继续主动增加规则，应用层、API 和页面将长期无法依赖稳定输入输出，项目会停留在算法工程而不是用户产品。

因此冻结 P1 对外契约。冻结不禁止修复缺陷和内部重构，而是要求任何会改变输入、输出、状态、拒绝码、约束或默认参数的修改显式升级版本并重新通过 Gate 6。

## 决策

### D1 冻结三个独立版本

```text
contract_version   = solver-p1-v1
constraint_version = constraints-p1-v1
parameter_version  = parameters-p1-2026-08-24
```

- 契约版本：输入、输出或机器可读词汇变化时升级；
- 约束版本：C1/C2/C4/C5/C6 或软目标语义变化时升级；
- 参数版本：默认阈值、成本、缓冲、时限变化时升级。

### D2 冻结 P1 硬约束和软目标

硬约束：

```text
C1 闭馆和日期例外
C2 开放时间、最晚入园、跨午夜和最低有效游览时长
C4 抵达/离开锚点
C5 极端天气排除室外
C6 非零、可追溯的交通衔接
```

软目标：

```text
S1 建议时长比例
S2 体力分天均衡和节奏提示
VISIT_PERIOD 游览时段偏好
DINNER_BLOCK 晚餐留白与降级
```

硬约束不可被任何软分补偿。

### D3 冻结默认参数

```text
speed/normal duration ratio = 0.6
leisure duration ratio      = 0.7
transit buffer ratio        = 1.2
route search time limit     = 2s/day solve
drop penalty                = 1,000,000
travel cost scale           = 30
period deviation cost       = 1/min
default day                 = 09:00–21:00
evening boundary            = 17:00
dinner preference           = 16:30–22:00
dinner full/reduced         = 90/60min
```

这些值是 P1 版本参数，不是永久业务真理。

### D4 冻结搜索和拒绝词汇

搜索状态保持：

```text
empty
completed
best_so_far
time_limit_no_solution
no_solution
invalid
```

拒绝码只允许追加兼容项；删除、改名或改变语义需要升级契约版本。应用层不得依赖 Python 异常文本展示用户错误。

### D5 冻结回放键

```text
input_snapshot_hash
+ data_snapshot_version
+ solver/contract_version
+ constraint_version
+ parameter_version
+ random_seed
= same structured output
```

P1 使用确定性主方案，不实现 ADR-0006 的替代候选池。

### D6 冻结后的允许修改

不升级契约版本即可进行：

- 不改变结果的内部重构；
- 性能优化且确定性结果不变；
- 测试、日志和文档增强；
- 用户文案翻译；
- Provider、API、数据库和 UI 适配；
- 修复不符合已冻结契约的实现缺陷。

必须先评审版本升级：

- 新增或改变硬约束；
- 改变时间桶边界；
- 改变默认成本、缓冲、时长比例或搜索时限；
- 改变拒绝码或搜索状态语义；
- 改变确定性与回放行为；
- 让受控多样性进入默认流程。

## 延期项

以下内容不阻塞 P1 应用设计：

- ADR-0006 受控多样性候选池；
- 多峰优选时段；
- 真实领域专家金标；
- 多城市生产数据验证；
- 高德/天气 API 的应用层接入；
- 微信登录、异步任务、数据库和 UI。

## 验收与后果

契约由 `DEFAULT_SOLVER_P1_CONTRACT` 和 `solver-p1-contract.json` 机器化保存，并由契约漂移测试保护。Gate 6 技术证据通过不等于 H3 已证实；真实专家和用户认可仍属于 G7。

冻结后求解器主线停止主动增加能力，下一阶段正式转入 P1 功能模块、信息架构和页面设计。只有页面或真实验证发现违反契约的缺陷时，才回到求解器修复。

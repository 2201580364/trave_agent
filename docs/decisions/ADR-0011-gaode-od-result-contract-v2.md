# ADR-0011：高德 OD 与行程结果契约 V2

- 状态：Accepted
- 日期：2026-08-26
- 产品里程碑：M1
- 实现优先级：P0
- 关联：ADR-0005、ADR-0009、ADR-0010、H3、C6

## 背景

ADR-0010 已决定把高德真实有向路网作为 M1 的正式 OD 来源，并允许外部 Provider 不可用时透明降级为近似 OD。`trip-result-v1` 只能表达交通耗时与数据依据，不能稳定表达本次新增的真实交通模式、道路距离和降级原因。若继续沿用 V1，应用层无法区分真实公交/步行/驾车与近似交通，也无法向用户如实解释高德失败后的结果来源。

本次没有改变 C1/C2/C4/C5/C6 的硬约束、S1/S2 的软目标，也没有改变求解默认参数；变化仅发生在 OD 快照构建和公开结果结构。

## 决策

当前版本组合升级为：

```text
solver contract    = solver-p1-v2
result schema      = trip-result-v2
constraint version = constraints-p1-v2
parameter version  = parameters-p1-2026-08-25
```

### D1 结果节点新增字段

有前序接驳的行程节点可以返回：

```text
transport_mode          walking | transit | driving
                        | walking_estimate | taxi_estimate
                        | transit_or_taxi_estimate
travel_distance_m       道路距离或明确标注的近似距离；未知时为 null
travel_fallback_reason  高德失败后使用近似 OD 的结构化原因；未降级时为 null
```

`travel_basis=gaode` 时不得携带 `travel_fallback_reason`。`travel_basis=approximate` 时，交通方式必须使用 estimate 口径，除非输入快照明确保存了其他可验证来源。

### D2 高德调用边界

高德 HTTP 调用只允许发生在 OD 快照构建阶段。构建完成后形成版本化、有向的 `TravelTimeResult` 集合，OR-Tools 求解阶段只读取内存或持久化快照，不在搜索循环中联网。

A→B 与 B→A 必须独立构建，不能假设道路距离、交通方式或耗时对称。缺边不能按 0 分钟补齐。

### D3 失败与透明降级

高德 timeout、rate limit、HTTP/API 错误、无路线或无效响应必须结构化分类。允许使用未过期缓存；缓存仍不可用时，可以使用近似 Provider，但必须同时满足：

1. `travel_basis=approximate`；
2. 保存 `travel_fallback_reason`；
3. 用户界面使用“估算”和区间表达；
4. 审计记录失败类别，但不记录 Key；
5. 无近似回退时保留 OD 缺边，由 C6 按不可连接处理。

### D4 凭证安全

高德 Web 服务 Key 仅从部署环境变量读取，不写入代码、数据库快照、行程结果、日志、审计载荷或配置对象 `repr`。错误信息不得拼接请求 URL 的 Key 参数。

### D5 历史兼容与不可变 Revision

保留历史机器标识和结果：

```text
solver-p1-v1
trip-result-v1
DEFAULT_SOLVER_P1_CONTRACT
```

历史 TripRevision 不迁移、不覆盖、不原地重算，查询时继续返回其原始版本。前端和应用读取层必须兼容 V1/V2；新生成结果使用 V2。V1 的 `p1` 仍只是历史兼容 ID，不代表产品优先级。

ADR-0010 的 D8 记录的是当时“输入输出结构未变”的历史判断，不回写修改；本 ADR 在新增公开结果字段后扩展并取代其当前版本结论。

## 影响

正向影响：

- 用户可以区分真实路网与估算数据；
- 页面可以展示交通方式和道路距离；
- 外部 Provider 失败原因可追踪、可测试、可审计；
- 求解阶段仍保持离线确定性和稳定回放。

成本与约束：

- API、前端类型、Gateway 映射和机器契约需要同步升级；
- V1/V2 需要并存读取；
- 真实联网验证需要部署环境提供高德 Web 服务 Key 和调用配额；
- 当前版本仍未实现餐厅真实节点、实时行中重排或地图导航详情。

## 验收

- V2 机器契约报告包含 `solver-p1-v2`；
- 高德结果映射出真实模式、`travel_distance_m` 和 `travel_basis=gaode`；
- 高德失败回退映射出 `travel_basis=approximate` 与结构化原因；
- A→B/B→A、缓存、超时、限流、缺边和模式选择均有离线测试；
- 全量、Golden、降级、接近度、数据校验、性能、TypeScript 与 H5 build 门禁重新通过；
- 日志、审计、结果和异常均不出现高德 Key。

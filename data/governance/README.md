# 数据来源治理资产

本目录保存可提交、非敏感、版本化的数据治理资产。它不保存 API Key、Cookie、登录态、原始评论、图片、视频或受限制页面副本。

## 当前资产

| 文件 | 用途 |
|---|---|
| `hangzhou-source-registry-v1.json` | 杭州 M1 首批来源、工程合规结论、字段级许可、条件和排除清单 |
| `place-collection-field-dictionary-v1.json` | 允许采集的 58 个地点、访问点、时间、体验、关系、OD、天气和来源字段 |
| `hangzhou-candidate-catalog-v1.json` | R0.2-04 的 72 个杭州候选、Provider 候选字段、覆盖标签和未裁决关系线索；全部为 candidate |
| `hangzhou-candidate-coverage-v1.json` | 从候选目录确定性派生的区域、类别、夜间、雨天、地点形态和退出门槛矩阵 |

校验：

```powershell
py -3.12 scripts/validate_source_registry.py --json
py -3.12 scripts/validate_candidate_catalog.py --json
```

## 版本规则

- 已被 published snapshot 或研究环境引用的 registry/dictionary 不原地覆盖；新增来源、权限扩大、字段语义变化时创建新版本。
- 纯错字修订若改变规范化 SHA-256，也必须同步测试和引用方，不能静默漂移。
- 每个数据采集批次绑定准确的 `registry_id + registry_sha256 + dictionary_id + dictionary_sha256`。
- R0.2-04 新增具体场馆、景区或公开攻略来源时，必须逐个登记；不能把“政府网站”“官方页面”作为无限通配授权。
- `conditional` 只允许进入 staging。只有 `approved` 来源的允许字段才可直接作为 published 事实来源，且仍需满足字段字典和 ADR-0018 的人工审核门禁。

完整规范见 [地点数据来源与采集规范](../../docs/domain/地点数据来源与采集规范.md)。

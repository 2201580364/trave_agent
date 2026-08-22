---
description: 按仓库证据检查 G0-G7 指定 Gate 是否可通过，并识别控制文件与 ADR/规格冲突
argument-hint: <Gate 编号，如 G4 或 G5>
---

读取 [Gate 规范](../../docs/process/gates.md)、最新 Accepted ADR、当前规格、领域规范、测试结果和假设登记册，检查 `$ARGUMENTS`：

1. 列出每条退出准则及 PASS / FAIL / NOT VERIFIED。
2. 为 PASS 提供仓库文件、测试命令或原始证据；不得只引用对话总结。
3. 列出开放 P0/P1、缺失证据和阻塞项。
4. 扫描 `CLAUDE.md`、rules、skills、agents 是否与最新 ADR/规格冲突。
5. 输出 Gate 结论：PASS / PASS WITH CONDITIONS / FAIL。

本命令默认只读；除非用户明确要求，不修改 Gate 状态、假设或实现文件。

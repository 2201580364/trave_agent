# 错误提示纪律（统一报错管线，2026-09-08 确立）

**适用**：任何涉及「新增/修改用户可见错误提示」的后端与前端改动。目的：所有报错走同一条管线，杜绝散落各处的临时文案、英文直出、details 泄漏。

## 一、管线总览（唯一合法路径）

```
稳定机器码 code（程序判断用，snake_case，进契约 §15.4 错误码表）
    ↓ application/common/error_messages.py（单一文案源）
中文用户文案 message（版本化，进 HTTP 响应）
    ↓ summarize_error_details（白名单 details 摘要自动拼接）
前端：服务器中文 message 优先 → code 兜底表 → 安全默认（三层）
```

## 二、硬规则

1. **文案单一来源**：用户可见错误文案只能写在 `src/travel_agent/application/common/error_messages.py` 的 `*_ERROR_MESSAGES` 表里。**禁止**在 errors.py 构造器、handlers、路由层、前端组件里硬编码新文案。规划侧与 admin 侧共用此文件（分表存放）。
2. **异常类不带文案**：`ApplicationError` 子类构造器只传 code 与结构化 details，message 由 `admin_error_message()`/`summarize_error_details()` 统一产出。新增错误类照抄 `ReviewRevisionNotApprovableError` 的模式。
3. **英文消息拦截**：domain 层 `ValueError`/不变量异常的 `str(exc)` 属英文技术词汇，**永不直出**。透传条件：message 含 CJK 字符（`_has_cjk` 判定），否则替换为该 code 的统一中文文案（见 `interfaces/http/app.py` 的 ValueError 处理器与 `common/errors.py` 的 state-transition 类）。
4. **details 白名单**：进用户文案的结构化字段必须在 `summarize_error_details` 白名单内（现有：`missing_checks`、`pending_review_checks`、`reason_codes`、`references`、`issues`、`not_candidate`）。新字段先加白名单再使用；**未入白名单的字段（含 SQL、堆栈、内部 ID）永不进 message**。
5. **前端只信 code**：
   - admin-web `src/api/errorMessages.ts`：新增错误码 = 在 `CODE_FALLBACKS` 加一条中文兜底（服务器正常时优先用服务器 message）。禁止在页面组件里各自 `catch` 写死文案。
   - 用户端 `frontend/src/shared/api/client.ts`：同样只维护 `CODE_FALLBACKS`；用户端直接展示 error.message，英文兜底文案必须覆盖该码。
6. **code 稳定即契约**：错误码一旦发布不可改名/删除，只能新增。新增码必须同步三处：`error_messages.py` 文案表 → 契约 §15.4 错误码表 → 两个前端 `CODE_FALLBACKS`。
7. **测试锁定**：新增码须在 `tests/application/test_error_messages.py` 补断言（文案存在、含 CJK、details 摘要正确、未知 details 不泄漏）。
8. **审计与展示分离**：`_reject` 审计事件的 `error_code` 保持纯机器码；人话摘要只进 HTTP 响应，不进审计（审计用结构化 reason_code/reason_text，另行维护）。

## 三、新增一个错误的完整清单

1. `application/common/error_messages.py`：加中文文案（必要时加 details 白名单字段与摘要渲染分支）
2. `application/**/errors.py`：新建/修改异常类，message 走统一管线
3. `docs/specs/api-contract.md` §15.4：登记错误码 + 触发条件 + details 结构
4. admin-web `errorMessages.ts` + frontend `client.ts`：各加一条 `CODE_FALLBACKS`
5. `tests/application/test_error_messages.py`：补文案与摘要断言
6. 相关业务测试补 HTTP 响应断言（code + details 结构，不断言完整 message 文本）

## 四、反例（禁止）

- ❌ 页面组件里 `catch (e) { message.error('保存失败，请重试') }`——绕过管线
- ❌ errors.py 里 `super().__init__("x_y", "某个新的中文文案")`——文案脱离单一来源
- ❌ 前端用正则/`includes` 解析后端英文 message 判断分支——改用 code
- ❌ 把 `str(exc)` 的英文直接透传给用户
- ❌ 复制粘贴别的错误类的文案而不登记 `error_messages.py`

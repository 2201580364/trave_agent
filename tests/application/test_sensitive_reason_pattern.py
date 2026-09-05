"""中文敏感词拦截回归测试（P0-1 乱码正则修复）。"""

from __future__ import annotations

import pytest

from travel_agent.application.admin.review import _SENSITIVE_REASON_PATTERN

# P0-1：review.py 的 _SENSITIVE_REASON_PATTERN 曾因 GBK 双重编码乱码，
# 导致中文凭证词（私钥/密码/令牌）静默失效。此测试确保修复不被回退。
CHINESE_SENSITIVE_WORDS = ["私钥", "密码", "令牌"]
ENGLISH_SENSITIVE_WORDS = [
    "api key",
    "api_key",
    "api-key",
    "access token",
    "password",
    "passwd",
    "cookie",
    "secret",
]
BENIGN_TEXTS = [
    "常规数据修订",
    "人工核对通过，维持既有结论",
    "更新营业时间与官方页面一致",
    "normal editorial note",
]


@pytest.mark.parametrize("word", CHINESE_SENSITIVE_WORDS)
def test_chinese_credential_word_is_blocked(word: str) -> None:
    assert _SENSITIVE_REASON_PATTERN.search(f"临时{word}是某个值") is not None
    assert _SENSITIVE_REASON_PATTERN.search(f"把{word}贴到这里") is not None


@pytest.mark.parametrize("word", ENGLISH_SENSITIVE_WORDS)
def test_english_credential_word_is_blocked(word: str) -> None:
    assert _SENSITIVE_REASON_PATTERN.search(f"临时 {word} 是某个值") is not None


@pytest.mark.parametrize("text", BENIGN_TEXTS)
def test_benign_text_is_not_blocked(text: str) -> None:
    assert _SENSITIVE_REASON_PATTERN.search(text) is None


def test_pattern_contains_no_mojibake() -> None:
    """模式串本身不得包含替换字符或 CJK 兼容区乱码特征。"""
    pattern_text = _SENSITIVE_REASON_PATTERN.pattern
    assert "\ufffd" not in pattern_text
    # GBK 双重编码乱码的典型特征：罕见 CJK 扩展区字符连串。
    # 正确版本只应包含「私钥|密码|令牌」三个常见词。
    for expected in ("私钥", "密码", "令牌"):
        assert expected in pattern_text

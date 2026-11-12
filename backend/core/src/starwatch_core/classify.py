"""把传输结果归类为成功、失败、拦截、空响应或超时。"""

from __future__ import annotations

from dataclasses import dataclass, field

from starwatch_core.constants import (
    CAPTCHA_MARKERS,
    CAPTCHA_SCAN_CHARS,
    HTTP_CLIENT_ERROR_MIN,
    HTTP_FORBIDDEN,
    HTTP_RATE_LIMITED,
)
from starwatch_core.schemas import Outcome


@dataclass(slots=True)
class RawExchange:
    """请求器返回的原始交换，尚未做任务语义判断。"""

    status_code: int | None = None
    headers: dict[str, str] = field(default_factory=dict)
    body: str = ""
    body_truncated: bool = False
    latency_ms: float | None = None
    final_url: str | None = None
    error_type: str | None = None
    error_message: str | None = None


@dataclass(frozen=True, slots=True)
class ProxyChoice:
    """一次请求实际使用的代理。url 为空表示直连。"""

    url: str | None
    label: str


@dataclass(frozen=True, slots=True)
class ClassifiedExchange:
    """传输层分类结果。"""

    outcome: Outcome
    error_type: str | None
    error_message: str | None


def classify_exchange(raw: RawExchange) -> ClassifiedExchange:
    """根据错误、状态码、验证码特征和空正文给出传输结果。

    Args:
        raw: 请求器返回的原始交换。

    Returns:
        不会把 403、429、验证码、空正文或超时说成普通成功。
    """
    if raw.error_type == "timeout":
        return ClassifiedExchange(Outcome.TIMEOUT, "timeout", raw.error_message or "请求超时")
    if raw.error_type:
        return ClassifiedExchange(
            Outcome.FAILURE,
            raw.error_type,
            raw.error_message or "请求失败",
        )
    if raw.status_code is None:
        return ClassifiedExchange(Outcome.FAILURE, "connection", "没有收到响应")
    if looks_like_captcha(raw.headers, raw.body):
        return ClassifiedExchange(Outcome.BLOCKED, "captcha", "响应看起来像验证码或挑战页")
    if raw.status_code == HTTP_FORBIDDEN:
        return ClassifiedExchange(Outcome.BLOCKED, "forbidden", "目标返回 403")
    if raw.status_code == HTTP_RATE_LIMITED:
        return ClassifiedExchange(Outcome.BLOCKED, "rate_limited", "目标返回 429")
    if raw.status_code >= HTTP_CLIENT_ERROR_MIN:
        return ClassifiedExchange(
            Outcome.FAILURE,
            "http_status",
            f"目标返回 HTTP {raw.status_code}",
        )
    if not raw.body.strip():
        return ClassifiedExchange(Outcome.EMPTY, "empty_body", "响应正文为空")
    return ClassifiedExchange(Outcome.SUCCESS, None, None)


def looks_like_captcha(headers: dict[str, str], body: str) -> bool:
    """用响应头和正文片段识别常见的验证码或挑战页。"""
    if headers.get("cf-mitigated"):
        return True
    sample = body[:CAPTCHA_SCAN_CHARS].lower()
    return any(marker in sample for marker in CAPTCHA_MARKERS)

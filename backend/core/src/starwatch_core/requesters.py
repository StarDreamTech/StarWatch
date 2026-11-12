"""httpx 请求器，以及浏览器、指纹和 DrissionPage 的存根。"""

from __future__ import annotations

import time
from collections.abc import Mapping

import httpx

from starwatch_core.classify import ProxyChoice, RawExchange
from starwatch_core.constants import DEFAULT_USER_AGENT, MAX_BODY_STORE_CHARS, REDACTED_HEADER_NAMES
from starwatch_core.errors import PluginNotImplementedError
from starwatch_core.schemas import RequestSpec
from starwatch_core.textutil import clip_text

ClientFactory = type[httpx.AsyncClient]


class HttpxRequester:
    """用 httpx 执行普通 HTTP 请求。"""

    name = "httpx"
    description = "基于 httpx 的 HTTP 请求器，支持常见方法、正文、Cookie、超时、重定向和 TLS 开关。"
    implemented = True

    def __init__(self, transport: httpx.AsyncBaseTransport | None = None) -> None:
        """创建请求器。

        Args:
            transport: 测试用的伪传输层。生产环境保持为空。
        """
        self._transport = transport

    async def execute(self, spec: RequestSpec, proxy: ProxyChoice) -> RawExchange:
        """执行一次请求。

        Args:
            spec: 请求描述。
            proxy: 本次使用的代理。

        Returns:
            含状态码、耗时、头和正文的原始交换。网络错误会写在 error_type 上。
        """
        headers = _with_user_agent(spec.headers)
        kwargs: dict[str, object] = {
            "timeout": httpx.Timeout(spec.timeout_seconds),
            "follow_redirects": spec.follow_redirects,
            "verify": spec.verify_tls,
            "headers": headers,
            "cookies": spec.cookies,
        }
        if self._transport is not None:
            kwargs["transport"] = self._transport
        elif proxy.url:
            kwargs["proxy"] = proxy.url
        started = time.perf_counter()
        try:
            async with httpx.AsyncClient(**kwargs) as client:  # type: ignore[arg-type]
                response = await client.request(
                    spec.method.value,
                    str(spec.url),
                    params=spec.query or None,
                    json=spec.json_body,
                    data=spec.form_body,
                    content=spec.raw_body.encode() if spec.raw_body is not None else None,
                )
        except httpx.HTTPError as exc:
            elapsed = _elapsed_ms(started)
            error_type = classify_transport_error(exc)
            return RawExchange(
                latency_ms=elapsed,
                final_url=str(spec.url),
                error_type=error_type,
                error_message=str(exc) or error_type,
            )
        body, truncated = clip_text(response.text, MAX_BODY_STORE_CHARS)
        return RawExchange(
            status_code=response.status_code,
            headers=public_headers(response.headers),
            body=body,
            body_truncated=truncated,
            latency_ms=_elapsed_ms(started),
            final_url=str(response.url),
        )


class _StubRequester:
    """已注册但尚未实现的请求器。调用时返回明确错误，而不是静默成功。"""

    implemented = False

    def __init__(self, name: str, description: str) -> None:
        """记录槽位名称和说明。"""
        self.name = name
        self.description = description

    async def execute(self, spec: RequestSpec, proxy: ProxyChoice) -> RawExchange:
        """拒绝执行。"""
        del spec, proxy
        raise PluginNotImplementedError(f"请求器 {self.name} 尚未实现，请改用 httpx")


def classify_transport_error(exc: httpx.HTTPError) -> str:
    """把 httpx 异常归到超时、代理、TLS、DNS 或连接失败。"""
    if isinstance(exc, httpx.TimeoutException):
        return "timeout"
    if isinstance(exc, httpx.ProxyError):
        return "proxy"
    text = str(exc).lower()
    if "certificate" in text or "tls" in text or "ssl" in text:
        return "tls"
    if "name or service" in text or "nodename" in text or "temporary failure in name" in text:
        return "dns"
    return "connection"


def public_headers(headers: Mapping[str, str]) -> dict[str, str]:
    """小写化响应头，并遮住凭证类字段。"""
    output: dict[str, str] = {}
    for key, value in headers.items():
        lowered = key.lower()
        output[lowered] = "***" if lowered in REDACTED_HEADER_NAMES else value
    return output


def _with_user_agent(headers: dict[str, str]) -> dict[str, str]:
    """在调用方没有指定时补上 StarWatch 的 User-Agent。"""
    copied = dict(headers)
    if not any(key.lower() == "user-agent" for key in copied):
        copied["User-Agent"] = DEFAULT_USER_AGENT
    return copied


def _elapsed_ms(started: float) -> float:
    """把 perf_counter 差值换成毫秒。"""
    return round((time.perf_counter() - started) * 1000, 2)


httpx_requester = HttpxRequester()
playwright_requester = _StubRequester(
    "playwright",
    "浏览器渲染（存根）。后续用 Playwright 打开页面并返回渲染后的 HTML。",
)
curl_cffi_requester = _StubRequester(
    "curl_cffi",
    "TLS 指纹模拟（存根）。后续用 curl_cffi 伪装浏览器握手。",
)
drissionpage_requester = _StubRequester(
    "drissionpage",
    "DrissionPage 浏览器控制（存根）。后续接入页面监听和渲染。",
)


def build_httpx() -> HttpxRequester:
    """入口点工厂：httpx。"""
    return httpx_requester


def build_playwright() -> _StubRequester:
    """入口点工厂：Playwright 存根。"""
    return playwright_requester


def build_curl_cffi() -> _StubRequester:
    """入口点工厂：curl_cffi 存根。"""
    return curl_cffi_requester


def build_drissionpage() -> _StubRequester:
    """入口点工厂：DrissionPage 存根。"""
    return drissionpage_requester

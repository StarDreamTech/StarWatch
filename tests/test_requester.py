"""httpx 请求器。"""

from __future__ import annotations

import httpx
import pytest

from starwatch_core.classify import ProxyChoice, classify_exchange
from starwatch_core.requesters import HttpxRequester
from starwatch_core.schemas import Outcome, RequestSpec


@pytest.mark.asyncio
async def test_httpx_sends_method_body_and_header() -> None:
    """请求方法、JSON 正文和默认 User-Agent 会送到传输层。"""
    seen: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["method"] = request.method
        seen["body"] = request.content.decode()
        seen["agent"] = request.headers["user-agent"]
        return httpx.Response(200, text="ok", headers={"Set-Cookie": "secret"})

    requester = HttpxRequester(transport=httpx.MockTransport(handler))
    raw = await requester.execute(
        RequestSpec(method="POST", url="https://example.com/hook", json_body={"n": 1}),
        ProxyChoice(url=None, label="direct"),
    )
    assert seen["method"] == "POST"
    assert '"n": 1' in seen["body"] or '"n":1' in seen["body"]
    assert seen["agent"].startswith("StarWatch/")
    assert raw.status_code == 200
    assert raw.headers["set-cookie"] == "***"
    assert classify_exchange(raw).outcome is Outcome.SUCCESS


@pytest.mark.asyncio
async def test_timeout_is_a_timeout_result() -> None:
    """超时不会被当成普通失败以外的成功。"""

    def handler(request: httpx.Request) -> httpx.Response:
        del request
        raise httpx.TimeoutException("timed out")

    requester = HttpxRequester(transport=httpx.MockTransport(handler))
    raw = await requester.execute(
        RequestSpec(url="https://example.com"),
        ProxyChoice(url=None, label="direct"),
    )
    classified = classify_exchange(raw)
    assert classified.outcome is Outcome.TIMEOUT
    assert classified.error_type == "timeout"

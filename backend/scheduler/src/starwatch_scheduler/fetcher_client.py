"""调度器访问抓取服务的客户端。调度器自己不发目标站请求。"""

from __future__ import annotations

from typing import Protocol

import httpx

from starwatch_core.errors import FetcherUnavailableError
from starwatch_core.schemas import FetchEnvelope, FetchRequest


class FetchClient(Protocol):
    """抓取客户端。测试可以换成直接返回结果的替身。"""

    async def open(self) -> None:
        """打开底层连接。"""

    async def close(self) -> None:
        """关闭底层连接。"""

    async def fetch(self, payload: FetchRequest) -> FetchEnvelope:
        """调用抓取器。"""


class HttpxFetchClient:
    """通过 HTTP 调用抓取器的 POST /fetch。"""

    def __init__(self, base_url: str, timeout_seconds: float) -> None:
        """记录抓取器地址。"""
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout_seconds
        self._client: httpx.AsyncClient | None = None

    async def open(self) -> None:
        """创建复用连接的客户端。"""
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=self._timeout)

    async def close(self) -> None:
        """关闭客户端。"""
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def fetch(self, payload: FetchRequest) -> FetchEnvelope:
        """POST 抓取请求。网络或协议错误变成 FetcherUnavailableError。"""
        if self._client is None:
            await self.open()
        assert self._client is not None
        try:
            response = await self._client.post(
                f"{self._base_url}/fetch",
                json=payload.model_dump(mode="json"),
            )
            response.raise_for_status()
            return FetchEnvelope.model_validate(response.json())
        except (httpx.HTTPError, ValueError) as exc:
            raise FetcherUnavailableError("抓取器不可用或返回了无法识别的结果") from exc

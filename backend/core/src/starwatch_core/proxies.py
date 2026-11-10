"""直连、静态代理、轮询代理池，以及外部代理池 API 的存根。"""

from __future__ import annotations

import asyncio
from collections.abc import Mapping
from urllib.parse import urlparse

from starwatch_core.classify import ProxyChoice
from starwatch_core.constants import PROXY_SCHEMES
from starwatch_core.errors import PluginNotImplementedError, ProxyConfigError


def parse_proxy_url(value: object) -> str:
    """校验 http、https 或 socks5 代理 URL。

    Args:
        value: 调用方传入的代理地址。

    Returns:
        去掉首尾空白后的地址。

    Raises:
        ProxyConfigError: 地址为空或协议不受支持。
    """
    if not isinstance(value, str) or not value.strip():
        raise ProxyConfigError("代理地址不能为空")
    text = value.strip()
    parsed = urlparse(text)
    if parsed.scheme not in PROXY_SCHEMES or not parsed.hostname:
        raise ProxyConfigError("代理地址需要是 http、https 或 socks5 URL")
    return text


class DirectProxy:
    """不使用代理。"""

    name = "direct"
    description = "直连，不经过代理。"
    implemented = True

    def validate(self, params: Mapping[str, object]) -> None:
        """直连没有必填参数。"""
        del params

    async def resolve(self, params: Mapping[str, object]) -> ProxyChoice:
        """返回直连。"""
        del params
        return ProxyChoice(url=None, label="direct")


class StaticProxy:
    """每次都使用同一个代理 URL。"""

    name = "static"
    description = "静态代理。参数 url 支持 http、https 和 socks5。"
    implemented = True

    def validate(self, params: Mapping[str, object]) -> None:
        """保存任务前检查 url。"""
        parse_proxy_url(params.get("url"))

    async def resolve(self, params: Mapping[str, object]) -> ProxyChoice:
        """返回配置的代理。"""
        url = parse_proxy_url(params.get("url"))
        return ProxyChoice(url=url, label=url)


class RotatingProxy:
    """在调用方提供的地址列表里轮询。每个进程维护自己的游标。"""

    name = "rotating"
    description = "轮询代理列表。参数 urls 是代理 URL 数组。"
    implemented = True

    def __init__(self) -> None:
        """创建进程内游标。"""
        self._cursors: dict[tuple[str, ...], int] = {}
        self._lock = asyncio.Lock()

    def validate(self, params: Mapping[str, object]) -> None:
        """保存任务前检查列表。"""
        _proxy_list(params)

    async def resolve(self, params: Mapping[str, object]) -> ProxyChoice:
        """按轮询顺序返回下一个代理。"""
        urls = _proxy_list(params)
        async with self._lock:
            index = self._cursors.get(urls, 0)
            choice = urls[index % len(urls)]
            self._cursors[urls] = index + 1
        return ProxyChoice(url=choice, label=choice)


class PoolApiProxy:
    """外部代理池的占位实现。

    约定接入时由 ``GET {endpoint}`` 返回 ``{"proxy": "http://ip:port"}``。
    当前版本只保留槽位，不发起请求。
    """

    name = "pool_api"
    description = "外部代理池 API（存根）。接入你自己的代理池时实现 ProxyProvider.resolve。"
    implemented = False

    def validate(self, params: Mapping[str, object]) -> None:
        """允许先把槽位保存下来，运行时再给出明确失败。"""
        del params

    async def resolve(self, params: Mapping[str, object]) -> ProxyChoice:
        """拒绝伪装成直连。"""
        del params
        raise PluginNotImplementedError(
            "外部代理池适配器尚未实现。请按 ProxyProvider 接口接入你的代理池，"
            '约定 GET {endpoint} 返回 {"proxy": "http://ip:port"}。'
        )


def _proxy_list(params: Mapping[str, object]) -> tuple[str, ...]:
    """读取并校验 urls 参数。"""
    raw = params.get("urls")
    if not isinstance(raw, list) or not raw:
        raise ProxyConfigError("轮询代理需要非空的 urls 列表")
    return tuple(parse_proxy_url(item) for item in raw)


direct_proxy = DirectProxy()
static_proxy = StaticProxy()
rotating_proxy = RotatingProxy()
pool_api_proxy = PoolApiProxy()


def build_direct() -> DirectProxy:
    """入口点工厂：直连。"""
    return direct_proxy


def build_static() -> StaticProxy:
    """入口点工厂：静态代理。"""
    return static_proxy


def build_rotating() -> RotatingProxy:
    """入口点工厂：轮询代理。"""
    return rotating_proxy


def build_pool_api() -> PoolApiProxy:
    """入口点工厂：外部代理池存根。"""
    return pool_api_proxy

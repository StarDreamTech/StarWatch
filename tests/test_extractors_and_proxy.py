"""提取器和代理槽位。"""

from __future__ import annotations

import pytest

from starwatch_core.errors import ExtractError, PluginNotImplementedError, ProxyConfigError
from starwatch_core.extractors import (
    css_extractor,
    jsonpath_extractor,
    regex_extractor,
    xpath_extractor,
)
from starwatch_core.proxies import direct_proxy, pool_api_proxy, rotating_proxy, static_proxy
from starwatch_core.schemas import ExtractRule


def test_extractors_pull_named_values() -> None:
    """四种提取器都能从示例文档里取出文本。"""
    html = "<html><h1>星哨</h1><a href='https://example.com'>链接</a></html>"
    assert css_extractor.extract(html, ExtractRule(name="title", kind="css", expression="h1")) == [
        "星哨"
    ]
    assert css_extractor.extract(
        html,
        ExtractRule(name="href", kind="css", expression="a", attribute="href"),
    ) == ["https://example.com"]
    assert xpath_extractor.extract(
        html, ExtractRule(name="title", kind="xpath", expression="//h1")
    ) == ["星哨"]
    body = '{"data": {"items": [{"name": "甲"}, {"name": "乙"}]}}'
    assert jsonpath_extractor.extract(
        body,
        ExtractRule(name="names", kind="jsonpath", expression="$.data.items[*].name"),
    ) == ["甲", "乙"]
    assert regex_extractor.extract(
        "价格 12 元", ExtractRule(name="price", kind="regex", expression=r"(\d+)")
    ) == ["12"]


def test_invalid_regex_is_rejected() -> None:
    """坏掉的正则在保存前就会失败。"""
    with pytest.raises(ExtractError):
        regex_extractor.validate(ExtractRule(name="bad", kind="regex", expression="("))


@pytest.mark.asyncio
async def test_proxy_providers() -> None:
    """直连、静态、轮询和代理池存根的行为稳定。"""
    direct = await direct_proxy.resolve({})
    assert direct.url is None
    static = await static_proxy.resolve({"url": "http://127.0.0.1:8088"})
    assert static.url == "http://127.0.0.1:8088"
    with pytest.raises(ProxyConfigError):
        static_proxy.validate({"url": "ftp://example.com"})
    first = await rotating_proxy.resolve({"urls": ["http://10.0.0.1:1", "socks5://10.0.0.2:2"]})
    second = await rotating_proxy.resolve({"urls": ["http://10.0.0.1:1", "socks5://10.0.0.2:2"]})
    assert first.url != second.url
    with pytest.raises(PluginNotImplementedError):
        await pool_api_proxy.resolve({"endpoint": "http://pool.internal"})

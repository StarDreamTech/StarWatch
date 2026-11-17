"""提取器和代理槽位。"""

from __future__ import annotations

import pytest

from starwatch_core.errors import ExtractError, PluginNotImplementedError, ProxyConfigError
from starwatch_core.extractors import (
    css_extractor,
    html_with_absolute_links,
    jsonpath_extractor,
    markdown_extractor,
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


def test_markdown_keeps_structure_images_and_absolute_links() -> None:
    html = """<html><head><base href="/docs/"></head><body><nav>忽略导航</nav>
    <article><h1>更新</h1><p><strong>重点</strong> <a href="../guide">指南</a></p>
    <ul><li>第一项</li></ul><img data-src="images/new.png" alt="新图">
    <script>alert('不要保留')</script></article></body></html>"""
    source = html_with_absolute_links(html, "https://example.com/redirected/page")
    rule = ExtractRule(name="正文", kind="markdown", expression="article")
    markdown_extractor.validate(rule)
    result = markdown_extractor.extract(source, rule)[0]
    assert "# 更新" in result
    assert "**重点**" in result
    assert "[指南](https://example.com/guide)" in result
    assert "![新图](https://example.com/docs/images/new.png)" in result
    assert "第一项" in result
    assert "忽略导航" not in result
    assert "不要保留" not in result
    with pytest.raises(ExtractError):
        markdown_extractor.validate(rule.model_copy(update={"attribute": "src"}))


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

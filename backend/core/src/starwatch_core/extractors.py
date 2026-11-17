"""CSS、XPath、JSONPath、正则与 HTML 转 Markdown 提取器。"""

from __future__ import annotations

import json
import re
from typing import Any

from jsonpath_ng.ext import parse as parse_jsonpath
from markdownify import markdownify
from parsel import Selector

from starwatch_core.constants import MAX_EXTRACT_MATCHES
from starwatch_core.errors import ExtractError
from starwatch_core.schemas import ExtractRule
from starwatch_core.textutil import normalize_lines

_TEXT_XPATH = "/text()"
_ATTR_XPATH = "/@"


class CssExtractor:
    """用 CSS 选择器提取文本或属性。"""

    name = "css"
    description = "CSS 选择器。默认取元素文本，也可以指定 attribute。"
    implemented = True

    def validate(self, rule: ExtractRule) -> None:
        """编译选择器，提前发现语法错误。"""
        try:
            Selector(text="<html></html>").css(rule.expression)
        except (ValueError, TypeError) as exc:
            raise ExtractError(f"CSS 选择器无效：{rule.expression}") from exc

    def extract(self, body: str, rule: ExtractRule) -> list[str]:
        """提取 CSS 匹配到的文本或属性。"""
        selector = Selector(text=body)
        if rule.attribute:
            values = [
                node.attrib.get(rule.attribute, "")
                for node in selector.css(rule.expression)
                if rule.attribute in node.attrib
            ]
            return normalize_lines(values)[:MAX_EXTRACT_MATCHES]
        expression = rule.expression if "::" in rule.expression else f"{rule.expression}::text"
        return normalize_lines(selector.css(expression).getall())[:MAX_EXTRACT_MATCHES]


class XPathExtractor:
    """用 XPath 提取节点字符串值或属性。"""

    name = "xpath"
    description = "XPath。默认取节点字符串值；表达式已含 /text() 或 /@ 时按原表达式取值。"
    implemented = True

    def validate(self, rule: ExtractRule) -> None:
        """编译 XPath。"""
        try:
            Selector(text="<html></html>").xpath(rule.expression)
        except (ValueError, TypeError) as exc:
            raise ExtractError(f"XPath 无效：{rule.expression}") from exc

    def extract(self, body: str, rule: ExtractRule) -> list[str]:
        """提取 XPath 匹配。"""
        selector = Selector(text=body)
        if rule.attribute:
            values = [
                node.attrib.get(rule.attribute, "")
                for node in selector.xpath(rule.expression)
                if rule.attribute in node.attrib
            ]
            return normalize_lines(values)[:MAX_EXTRACT_MATCHES]
        expression = rule.expression.strip()
        if expression.endswith(_TEXT_XPATH) or _ATTR_XPATH in expression:
            values = selector.xpath(expression).getall()
        else:
            values = selector.xpath(expression).xpath("string(.)").getall()
        return normalize_lines(values)[:MAX_EXTRACT_MATCHES]


class JsonPathExtractor:
    """用 JSONPath 从 JSON 正文取值。"""

    name = "jsonpath"
    description = "JSONPath，例如 $.data.items[*].name。"
    implemented = True

    def validate(self, rule: ExtractRule) -> None:
        """编译 JSONPath。"""
        try:
            parse_jsonpath(rule.expression)
        except Exception as exc:
            raise ExtractError(f"JSONPath 无效：{rule.expression}") from exc

    def extract(self, body: str, rule: ExtractRule) -> list[str]:
        """解析 JSON 并返回匹配值的字符串形式。"""
        try:
            payload = json.loads(body)
        except json.JSONDecodeError as exc:
            raise ExtractError("响应不是合法 JSON，无法使用 JSONPath") from exc
        matches = parse_jsonpath(rule.expression).find(payload)
        values = [_stringify(match.value) for match in matches]
        return normalize_lines(values)[:MAX_EXTRACT_MATCHES]


class RegexExtractor:
    """用正则表达式提取捕获结果。"""

    name = "regex"
    description = "Python 正则。有捕获组时拼接各个分组。"
    implemented = True

    def validate(self, rule: ExtractRule) -> None:
        """编译正则。"""
        try:
            re.compile(rule.expression)
        except re.error as exc:
            raise ExtractError(f"正则无效：{exc}") from exc

    def extract(self, body: str, rule: ExtractRule) -> list[str]:
        """返回 findall 的结果。"""
        try:
            found = re.findall(rule.expression, body)
        except re.error as exc:
            raise ExtractError(f"正则无效：{exc}") from exc
        values: list[str] = []
        for item in found[:MAX_EXTRACT_MATCHES]:
            if isinstance(item, tuple):
                values.append(" ".join(part for part in item if part))
            else:
                values.append(str(item))
        return normalize_lines(values)


class MarkdownExtractor:
    """把 CSS 选择的 HTML 区域转换成保留图片和链接的 Markdown。"""

    name = "markdown"
    description = "CSS 选择 HTML 区域并转为 Markdown，保留标题、列表、图片和链接。"
    implemented = True

    def validate(self, rule: ExtractRule) -> None:
        """Markdown 选择器必须选择元素，不能提取文本或属性。"""
        if rule.attribute or "::" in rule.expression:
            raise ExtractError("Markdown 提取需要 CSS 元素选择器，不能指定属性或伪元素")
        css_extractor.validate(rule)

    def extract(self, body: str, rule: ExtractRule) -> list[str]:
        """转换选中区域，保持 Markdown 的段落和代码换行。"""
        values = [
            markdownify(
                node.get(),
                heading_style="ATX",
                autolinks=False,
                keep_inline_images_in=["a", "td", "th", "h1", "h2", "h3", "h4", "h5", "h6"],
            )
            for node in Selector(text=body).css(rule.expression)[:MAX_EXTRACT_MATCHES]
        ]
        return normalize_lines(values)


def html_with_absolute_links(body: str, base_url: str) -> str:
    """以最终响应地址及 HTML base 为基准，补全链接和懒加载图片地址。"""
    selector = Selector(text=body)
    for image in selector.css("img"):
        if not image.attrib.get("src"):
            source = image.attrib.get("data-src") or image.attrib.get("data-original")
            if source:
                image.root.set("src", source)
    selector.root.make_links_absolute(base_url, resolve_base_href=True)
    return str(selector.get())


def _stringify(value: Any) -> str:
    """把 JSON 值转成稳定的比较文本。"""
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


css_extractor = CssExtractor()
xpath_extractor = XPathExtractor()
jsonpath_extractor = JsonPathExtractor()
regex_extractor = RegexExtractor()
markdown_extractor = MarkdownExtractor()


def build_css() -> CssExtractor:
    """入口点工厂：CSS 提取器。"""
    return css_extractor


def build_xpath() -> XPathExtractor:
    """入口点工厂：XPath 提取器。"""
    return xpath_extractor


def build_jsonpath() -> JsonPathExtractor:
    """入口点工厂：JSONPath 提取器。"""
    return jsonpath_extractor


def build_regex() -> RegexExtractor:
    """入口点工厂：正则提取器。"""
    return regex_extractor


def build_markdown() -> MarkdownExtractor:
    """入口点工厂：HTML 转 Markdown 提取器。"""
    return markdown_extractor

"""文本截断与空白归一。"""

from __future__ import annotations


def clip_text(value: str, limit: int) -> tuple[str, bool]:
    """按字符数截断文本。

    Args:
        value: 原始文本。
        limit: 允许保留的最大字符数。

    Returns:
        截断后的文本，以及是否发生了截断。
    """
    if len(value) <= limit:
        return value, False
    return value[:limit], True


def normalize_lines(values: list[str]) -> list[str]:
    """去掉每条结果首尾空白，并丢弃空字符串。"""
    return [item.strip() for item in values if item and item.strip()]

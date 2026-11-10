"""统一日志格式。不记录响应正文。"""

from __future__ import annotations

import logging


def configure_logging(level: str) -> None:
    """按名称设置根日志级别。

    Args:
        level: 例如 INFO、DEBUG。无法识别时回退到 INFO。
    """
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )

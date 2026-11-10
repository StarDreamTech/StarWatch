"""进程内滑动窗口限流。足够挡住误操作，不替代网关。"""

from __future__ import annotations

import asyncio
import time
from collections import deque


class RateLimiter:
    """按键统计一个时间窗内的请求次数。"""

    def __init__(self, limit: int, window_seconds: int) -> None:
        """创建限流器。

        Args:
            limit: 窗口内允许的请求数。小于等于 0 时不限制。
            window_seconds: 窗口长度，单位秒。
        """
        self.limit = limit
        self.window_seconds = window_seconds
        self._hits: dict[str, deque[float]] = {}
        self._lock = asyncio.Lock()

    async def allow(self, key: str) -> bool:
        """记录一次访问。返回是否放行。"""
        if self.limit <= 0:
            return True
        now = time.monotonic()
        async with self._lock:
            bucket = self._hits.setdefault(key, deque())
            cutoff = now - self.window_seconds
            while bucket and bucket[0] <= cutoff:
                bucket.popleft()
            if len(bucket) >= self.limit:
                return False
            bucket.append(now)
            return True

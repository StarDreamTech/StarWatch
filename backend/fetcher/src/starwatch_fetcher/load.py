"""在抓取器进程内执行有上限的饱和请求。"""

from __future__ import annotations

import asyncio
import math
import time

from starwatch_core.classify import ProxyChoice
from starwatch_core.constants import (
    LOAD_SAMPLE_LIMIT,
    MAX_LOAD_REQUESTS,
    PERCENTILE_P50,
    PERCENTILE_P95,
)
from starwatch_core.protocols import Requester
from starwatch_core.schemas import (
    FetchEnvelope,
    LoadSample,
    LoadSpec,
    LoadSummary,
    Outcome,
    RequestSpec,
)


async def run_load(
    requester: Requester,
    spec: RequestSpec,
    proxy: ProxyChoice,
    load: LoadSpec,
) -> FetchEnvelope:
    """按并发和 QPS 发出一批请求并汇总。

    Args:
        requester: 已解析的请求器。
        spec: 单次请求描述。
        proxy: 本批请求共用的代理。
        load: 并发、速率和停止条件。

    Returns:
        顶层 outcome 表示整批结果，samples 只保留少量状态。
    """
    target = min(load.request_count or MAX_LOAD_REQUESTS, MAX_LOAD_REQUESTS)
    deadline = time.monotonic() + load.duration_seconds if load.duration_seconds else None
    interval = (1 / load.qps) if load.qps else 0.0
    semaphore = asyncio.Semaphore(load.concurrency)
    tasks: list[asyncio.Task[FetchEnvelope]] = []
    started = 0
    while started < target:
        if deadline is not None and time.monotonic() >= deadline:
            break
        await semaphore.acquire()
        tasks.append(asyncio.create_task(_one(semaphore, requester, spec, proxy)))
        started += 1
        if interval and started < target:
            await asyncio.sleep(interval)
    results = list(await asyncio.gather(*tasks))
    return _aggregate(results, requester.name, proxy.label)


async def _one(
    semaphore: asyncio.Semaphore,
    requester: Requester,
    spec: RequestSpec,
    proxy: ProxyChoice,
) -> FetchEnvelope:
    """发出单次请求，并在结束后释放并发名额。"""
    try:
        from starwatch_fetcher.service import envelope_from_exchange

        raw = await requester.execute(spec, proxy)
        return envelope_from_exchange(raw, {}, requester.name, proxy.label, load=None)
    finally:
        semaphore.release()


def _aggregate(results: list[FetchEnvelope], requester: str, proxy_label: str) -> FetchEnvelope:
    """把单次结果收成汇总。空响应计入失败；整批都为空时结果是 empty。"""
    if not results:
        return FetchEnvelope(
            outcome=Outcome.FAILURE,
            error_type="load_empty",
            error_message="没有在截止时间前发出请求",
            requester=requester,
            proxy_label=proxy_label,
        )
    succeeded = failed = blocked = timeouts = empty = 0
    latencies: list[float] = []
    histogram: dict[str, int] = {}
    for item in results:
        key = (
            str(item.status_code)
            if item.status_code is not None
            else (item.error_type or item.outcome.value)
        )
        histogram[key] = histogram.get(key, 0) + 1
        if item.latency_ms is not None:
            latencies.append(item.latency_ms)
        if item.outcome is Outcome.SUCCESS:
            succeeded += 1
        elif item.outcome is Outcome.BLOCKED:
            blocked += 1
        elif item.outcome is Outcome.TIMEOUT:
            timeouts += 1
        elif item.outcome is Outcome.EMPTY:
            empty += 1
            failed += 1
        else:
            failed += 1
    total = len(results)
    outcome = _overall(total, succeeded, blocked, timeouts, empty)
    summary = LoadSummary(
        total=total,
        succeeded=succeeded,
        failed=failed,
        blocked=blocked,
        timeouts=timeouts,
        latency_ms_p50=_percentile(latencies, PERCENTILE_P50),
        latency_ms_p95=_percentile(latencies, PERCENTILE_P95),
        status_histogram=histogram,
        samples=[
            LoadSample(
                status_code=item.status_code,
                outcome=item.outcome,
                latency_ms=item.latency_ms,
                error_type=item.error_type,
            )
            for item in results[:LOAD_SAMPLE_LIMIT]
        ],
    )
    error_type = None if outcome is Outcome.SUCCESS else outcome.value
    return FetchEnvelope(
        outcome=outcome,
        error_type=error_type,
        error_message=None if outcome is Outcome.SUCCESS else "压测存在失败、拦截、超时或空响应",
        requester=requester,
        proxy_label=proxy_label,
        load=summary,
        latency_ms=summary.latency_ms_p50,
    )


def _overall(total: int, succeeded: int, blocked: int, timeouts: int, empty: int) -> Outcome:
    """整批请求只在全部同态时使用该状态，混合结果记为失败。"""
    if succeeded == total:
        return Outcome.SUCCESS
    if blocked == total:
        return Outcome.BLOCKED
    if timeouts == total:
        return Outcome.TIMEOUT
    if empty == total:
        return Outcome.EMPTY
    return Outcome.FAILURE


def _percentile(values: list[float], percent: int) -> float | None:
    """最近秩百分位。没有样本时返回空。"""
    if not values:
        return None
    ordered = sorted(values)
    rank = math.ceil(percent / 100 * len(ordered)) - 1
    rank = min(max(rank, 0), len(ordered) - 1)
    return ordered[rank]

"""把请求器、代理和提取器串成一次归一化抓取。"""

from __future__ import annotations

import asyncio
from typing import cast

from starwatch_core.bootstrap import extractors, proxies, register_builtins, requesters
from starwatch_core.classify import ClassifiedExchange, RawExchange, classify_exchange
from starwatch_core.errors import ExtractError, PluginNotImplementedError, ProxyConfigError
from starwatch_core.protocols import Extractor, ProxyProvider, Requester
from starwatch_core.schemas import FetchEnvelope, FetchRequest, LoadSummary, Outcome


class FetchService:
    """无状态抓取。不写数据库。"""

    async def execute(self, payload: FetchRequest) -> FetchEnvelope:
        """按任务选择的插件执行一次抓取或一小段压测。

        Args:
            payload: 调度器发来的请求描述。

        Returns:
            归一化结果。未实现的插件会变成明确的失败，而不是空成功。
        """
        register_builtins()
        requester = cast(Requester, requesters.get(payload.requester.name))
        provider = cast(ProxyProvider, proxies.get(payload.proxy.provider))
        if not requester.implemented:
            return _failed(
                payload,
                "requester_unavailable",
                f"请求器 {payload.requester.name} 尚未实现",
            )
        try:
            proxy = await provider.resolve(payload.proxy.params)
        except PluginNotImplementedError as exc:
            return _failed(payload, "proxy_unavailable", str(exc))
        except ProxyConfigError as exc:
            return _failed(payload, "invalid_proxy", exc.message)
        if payload.load is not None and payload.task_type.value == "load_test":
            from starwatch_fetcher.load import run_load

            return await run_load(requester, payload.request, proxy, payload.load)
        try:
            raw = await requester.execute(payload.request, proxy)
        except PluginNotImplementedError as exc:
            return _failed(payload, "requester_unavailable", str(exc))
        extracted, extract_error = await _extract(payload, raw.body)
        envelope = envelope_from_exchange(raw, extracted, requester.name, proxy.label, load=None)
        if extract_error and envelope.outcome is Outcome.SUCCESS:
            return envelope.model_copy(
                update={
                    "outcome": Outcome.FAILURE,
                    "error_type": "extract",
                    "error_message": extract_error,
                }
            )
        return envelope


def envelope_from_exchange(
    raw: RawExchange,
    extracted: dict[str, list[str]],
    requester: str,
    proxy_label: str,
    load: LoadSummary | None,
) -> FetchEnvelope:
    """把原始交换和分类结果收成抓取器响应。"""
    classified: ClassifiedExchange = classify_exchange(raw)
    return FetchEnvelope(
        outcome=classified.outcome,
        error_type=classified.error_type,
        error_message=classified.error_message,
        status_code=raw.status_code,
        latency_ms=raw.latency_ms,
        headers=raw.headers,
        body=raw.body,
        body_truncated=raw.body_truncated,
        extracted=extracted,
        final_url=raw.final_url,
        requester=requester,
        proxy_label=proxy_label,
        load=load,
    )


async def _extract(payload: FetchRequest, body: str) -> tuple[dict[str, list[str]], str | None]:
    """执行全部提取规则。编译期没有拦住的运行时错误返回说明。"""
    extracted: dict[str, list[str]] = {}
    for rule in payload.extract_rules:
        extractor = cast(Extractor, extractors.get(rule.kind))
        try:
            extracted[rule.name] = await asyncio.to_thread(extractor.extract, body, rule)
        except ExtractError as exc:
            return extracted, exc.message
    return extracted, None


def _failed(payload: FetchRequest, error_type: str, message: str) -> FetchEnvelope:
    """构造没有发生网络请求的失败结果。"""
    return FetchEnvelope(
        outcome=Outcome.FAILURE,
        error_type=error_type,
        error_message=message,
        requester=payload.requester.name,
        proxy_label=payload.proxy.provider,
    )

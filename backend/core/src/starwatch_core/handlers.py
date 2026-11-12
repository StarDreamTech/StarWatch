"""网页变化、接口探活和压测三类任务的结果解释。"""

from __future__ import annotations

import json

from jsonpath_ng.ext import parse as parse_jsonpath

from starwatch_core.constants import EMPTY_SUCCESS_STATUSES
from starwatch_core.diff import diff_snapshots
from starwatch_core.errors import ExtractError
from starwatch_core.schemas import (
    AssertionSpec,
    FetchEnvelope,
    NotifyCategory,
    Outcome,
    Task,
    TaskEvaluation,
)
from starwatch_core.textutil import normalize_lines

_TRANSPORT_FAILURES = frozenset(
    {
        "connection",
        "dns",
        "tls",
        "proxy",
        "requester_unavailable",
        "proxy_unavailable",
        "extract",
        "fetcher_unavailable",
    }
)


class PageChangeHandler:
    """比较提取字段。拦截、超时和空结果不会记成无变化。"""

    name = "page_change"
    description = "按 CSS、XPath、JSONPath 或正则提取字段，并与上一份快照比较。"
    implemented = True

    def evaluate(
        self,
        task: Task,
        envelope: FetchEnvelope,
        previous: dict[str, list[str]] | None,
    ) -> TaskEvaluation:
        """给出基线、变化、无变化，或保留传输失败状态。"""
        if not task.extract_rules:
            return _terminal(
                Outcome.FAILURE,
                "网页监控至少需要一条提取规则",
                "config",
                notify=True,
                category="failure",
            )
        blocked = _transport_terminal(envelope)
        if blocked is not None:
            return blocked
        if envelope.outcome is Outcome.EMPTY or _all_empty(task, envelope):
            return _terminal(
                Outcome.EMPTY,
                "页面正文或提取结果为空",
                envelope.error_type or "empty_extract",
                notify=True,
                category="block",
            )
        if previous is None:
            return TaskEvaluation(
                outcome=Outcome.BASELINE,
                summary="已建立基线",
                snapshot=envelope.extracted,
            )
        diff = diff_snapshots(previous, envelope.extracted)
        if diff.changed:
            names = [item.name for item in diff.fields if item.status != "unchanged"]
            return TaskEvaluation(
                outcome=Outcome.CHANGED,
                summary=f"字段发生变化：{'、'.join(names)}",
                diff=diff,
                snapshot=envelope.extracted,
                notify=True,
                notify_category="change",
            )
        return TaskEvaluation(
            outcome=Outcome.UNCHANGED,
            summary="监控字段没有变化",
            diff=diff,
            snapshot=envelope.extracted,
        )


class ApiCheckHandler:
    """按状态码、耗时、正文、JSONPath 和响应头做断言。"""

    name = "api_check"
    description = "检查状态码、耗时、正文片段、JSONPath 或响应头。"
    implemented = True

    def evaluate(
        self,
        task: Task,
        envelope: FetchEnvelope,
        previous: dict[str, list[str]] | None,
    ) -> TaskEvaluation:
        """断言失败和传输失败都记为失败，不与历史结果比较。"""
        del previous
        if envelope.outcome in {Outcome.TIMEOUT, Outcome.BLOCKED}:
            return _transport_terminal(envelope) or _terminal(
                envelope.outcome,
                envelope.error_message or envelope.outcome.value,
                envelope.error_type,
                notify=True,
                category="failure" if envelope.outcome is Outcome.TIMEOUT else "block",
            )
        if envelope.error_type in _TRANSPORT_FAILURES:
            return _transport_terminal(envelope) or _terminal(
                Outcome.FAILURE,
                envelope.error_message or "请求失败",
                envelope.error_type,
                notify=True,
                category="failure",
            )
        errors = _assertion_errors(task.assertions, envelope)
        expects_status = _expects_status(task.assertions, envelope.status_code)
        if envelope.outcome is Outcome.FAILURE and not expects_status:
            detail = envelope.error_message or "接口返回异常状态"
            if errors:
                detail = f"{detail}；" + "；".join(errors)
            return _terminal(
                Outcome.FAILURE, detail, "http_status", notify=True, category="failure"
            )
        if errors:
            return _terminal(
                Outcome.FAILURE,
                "；".join(errors),
                "assertion",
                notify=True,
                category="failure",
            )
        if envelope.outcome is Outcome.EMPTY and not _empty_allowed(task, envelope):
            return _terminal(
                Outcome.EMPTY,
                "接口返回空正文",
                "empty_body",
                notify=True,
                category="block",
            )
        latency = envelope.latency_ms if envelope.latency_ms is not None else 0
        return TaskEvaluation(
            outcome=Outcome.SUCCESS,
            summary=f"探活通过，HTTP {envelope.status_code}，{latency:.0f} ms",
        )


class LoadTestHandler:
    """汇总饱和请求。只要有失败、拦截或超时，就不会记成无变化。"""

    name = "load_test"
    description = "按并发和 QPS 发送一批请求，并汇总状态码与延迟。"
    implemented = True

    def evaluate(
        self,
        task: Task,
        envelope: FetchEnvelope,
        previous: dict[str, list[str]] | None,
    ) -> TaskEvaluation:
        """把抓取器的汇总翻译成运行结果。"""
        del task, previous
        summary = _load_text(envelope)
        if envelope.outcome is Outcome.SUCCESS:
            return TaskEvaluation(outcome=Outcome.SUCCESS, summary=summary)
        category: NotifyCategory = "failure"
        if envelope.outcome in {Outcome.BLOCKED, Outcome.EMPTY}:
            category = "block"
        return _terminal(
            envelope.outcome if envelope.outcome is not Outcome.UNCHANGED else Outcome.FAILURE,
            summary,
            envelope.error_type or envelope.outcome.value,
            notify=True,
            category=category,
        )


def _transport_terminal(envelope: FetchEnvelope) -> TaskEvaluation | None:
    """拦截、超时和无响应直接成为最终结果。"""
    if envelope.outcome is Outcome.TIMEOUT:
        return _terminal(
            Outcome.TIMEOUT,
            envelope.error_message or "请求超时",
            "timeout",
            notify=True,
            category="failure",
        )
    if envelope.outcome is Outcome.BLOCKED:
        return _terminal(
            Outcome.BLOCKED,
            envelope.error_message or "请求被拦截",
            envelope.error_type or "blocked",
            notify=True,
            category="block",
        )
    if envelope.outcome is Outcome.FAILURE or envelope.error_type in _TRANSPORT_FAILURES:
        return _terminal(
            Outcome.FAILURE,
            envelope.error_message or "请求失败",
            envelope.error_type or "failure",
            notify=True,
            category="failure",
        )
    return None


def _terminal(
    outcome: Outcome,
    summary: str,
    error_type: str | None,
    *,
    notify: bool,
    category: NotifyCategory,
) -> TaskEvaluation:
    """构造一个不再比较快照的结果。"""
    return TaskEvaluation(
        outcome=outcome,
        summary=summary,
        error_type=error_type,
        error_message=summary,
        notify=notify,
        notify_category=category,
    )


def _all_empty(task: Task, envelope: FetchEnvelope) -> bool:
    """每条提取规则都没有命中。"""
    return all(not envelope.extracted.get(rule.name) for rule in task.extract_rules)


def _expects_status(assertions: list[AssertionSpec], status_code: int | None) -> bool:
    """是否有断言明确期待当前状态码。"""
    if status_code is None:
        return False
    expected = str(status_code)
    return any(item.kind == "status" and item.expected == expected for item in assertions)


def _empty_allowed(task: Task, envelope: FetchEnvelope) -> bool:
    """204/205 或明确断言了这些状态码时，空正文算成功。"""
    if envelope.status_code in EMPTY_SUCCESS_STATUSES:
        return True
    return any(
        item.kind == "status" and item.expected in {"204", "205"} for item in task.assertions
    )


def _assertion_errors(assertions: list[AssertionSpec], envelope: FetchEnvelope) -> list[str]:
    """收集未通过的断言说明。"""
    errors: list[str] = []
    for item in assertions:
        if item.kind == "status" and str(envelope.status_code) != item.expected:
            errors.append(f"状态码是 {envelope.status_code}，期望 {item.expected}")
        elif item.kind == "latency_ms":
            limit = float(item.expected)
            latency = envelope.latency_ms if envelope.latency_ms is not None else limit + 1
            if latency > limit:
                errors.append(f"耗时 {latency:.0f} ms，超过 {item.expected} ms")
        elif item.kind == "body_contains" and item.expected not in envelope.body:
            errors.append(f"正文不包含「{item.expected}」")
        elif item.kind == "header":
            actual = _header_value(envelope.headers, item.path or "")
            if actual != item.expected:
                errors.append(f"响应头 {item.path} 是「{actual}」，期望「{item.expected}」")
        elif item.kind == "jsonpath":
            values = _json_values(envelope.body, item.path or "")
            if item.expected not in values:
                errors.append(f"JSONPath {item.path} 未得到「{item.expected}」")
    return errors


def _header_value(headers: dict[str, str], name: str) -> str:
    """按小写名称读取响应头。"""
    target = name.lower()
    for key, value in headers.items():
        if key.lower() == target:
            return value
    return ""


def _json_values(body: str, expression: str) -> list[str]:
    """执行 JSONPath。正文不是 JSON 时视为断言失败。"""
    try:
        payload = json.loads(body) if body else None
        matches = parse_jsonpath(expression).find(payload)
    except json.JSONDecodeError, TypeError, ExtractError:
        return []
    except Exception:
        return []
    values: list[str] = []
    for match in matches:
        value = match.value
        if isinstance(value, str):
            values.append(value)
        else:
            values.append(json.dumps(value, ensure_ascii=False, sort_keys=True))
    return normalize_lines(values)


def _load_text(envelope: FetchEnvelope) -> str:
    """用汇总数字生成压测说明。"""
    load = envelope.load
    if load is None:
        return envelope.error_message or "压测没有返回汇总"
    return (
        f"共 {load.total} 次，成功 {load.succeeded}，失败 {load.failed}，"
        f"拦截 {load.blocked}，超时 {load.timeouts}"
    )


page_change_handler = PageChangeHandler()
api_check_handler = ApiCheckHandler()
load_test_handler = LoadTestHandler()


def build_page_change() -> PageChangeHandler:
    """入口点工厂：网页监控。"""
    return page_change_handler


def build_api_check() -> ApiCheckHandler:
    """入口点工厂：接口探活。"""
    return api_check_handler


def build_load_test() -> LoadTestHandler:
    """入口点工厂：压测。"""
    return load_test_handler

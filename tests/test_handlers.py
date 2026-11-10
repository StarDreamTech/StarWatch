"""任务结果解释。拦截和空结果不能变成无变化。"""

from __future__ import annotations

from datetime import UTC, datetime

from starwatch_core.handlers import api_check_handler, page_change_handler
from starwatch_core.schemas import (
    AssertionSpec,
    ExtractRule,
    FetchEnvelope,
    NotifySpec,
    Outcome,
    ProxyConfig,
    RequesterConfig,
    RequestSpec,
    Schedule,
    ScheduleKind,
    Task,
    TaskType,
)


def _task(task_type: TaskType = TaskType.PAGE_CHANGE) -> Task:
    """构造一条最小任务。"""
    now = datetime(2026, 1, 1, tzinfo=UTC)
    return Task(
        id="task-1",
        name="首页",
        description="",
        enabled=True,
        schedule=Schedule(
            kind=ScheduleKind.INTERVAL, expression="every 1 minute", interval_seconds=60
        ),
        task_type=task_type,
        request=RequestSpec(url="https://example.com"),
        requester=RequesterConfig(),
        proxy=ProxyConfig(),
        extract_rules=[ExtractRule(name="title", kind="css", expression="h1")],
        assertions=[AssertionSpec(kind="status", expected="200")],
        load=None,
        notify=NotifySpec(),
        next_run_at=now,
        created_at=now,
        updated_at=now,
    )


def _envelope(**updates: object) -> FetchEnvelope:
    """构造抓取结果。"""
    base = FetchEnvelope(
        outcome=Outcome.SUCCESS, requester="httpx", proxy_label="direct", status_code=200
    )
    return base.model_copy(update=updates)


def test_blocked_page_is_not_unchanged() -> None:
    """403 保持拦截，即使以前有快照。"""
    evaluation = page_change_handler.evaluate(
        _task(),
        _envelope(
            outcome=Outcome.BLOCKED,
            error_type="forbidden",
            error_message="目标返回 403",
            status_code=403,
            body="forbidden",
        ),
        {"title": ["旧标题"]},
    )
    assert evaluation.outcome is Outcome.BLOCKED
    assert evaluation.snapshot is None
    assert evaluation.notify_category == "block"


def test_page_baseline_then_change() -> None:
    """第一次成功建立基线，字段不同才算变化。"""
    task = _task()
    baseline = page_change_handler.evaluate(
        task, _envelope(extracted={"title": ["甲"]}, body="甲"), None
    )
    assert baseline.outcome is Outcome.BASELINE
    same = page_change_handler.evaluate(
        task,
        _envelope(extracted={"title": ["甲"]}, body="甲"),
        {"title": ["甲"]},
    )
    assert same.outcome is Outcome.UNCHANGED
    changed = page_change_handler.evaluate(
        task,
        _envelope(extracted={"title": ["乙"]}, body="乙"),
        {"title": ["甲"]},
    )
    assert changed.outcome is Outcome.CHANGED
    assert changed.diff is not None
    assert changed.diff.changed is True


def test_empty_extract_is_empty_not_unchanged() -> None:
    """选择器没有命中时不能记成无变化。"""
    evaluation = page_change_handler.evaluate(
        _task(),
        _envelope(extracted={"title": []}, body="<html></html>"),
        {"title": ["甲"]},
    )
    assert evaluation.outcome is Outcome.EMPTY


def test_api_assertion_failure_and_expected_status() -> None:
    """断言失败可见；明确期待的 404 可以通过。"""
    task = _task(TaskType.API_CHECK)
    failed = api_check_handler.evaluate(
        task,
        _envelope(status_code=500, outcome=Outcome.FAILURE, error_type="http_status", body="no"),
        None,
    )
    assert failed.outcome is Outcome.FAILURE
    assert failed.error_type == "http_status"
    task.assertions.append(AssertionSpec(kind="body_contains", expected="missing"))
    ok = api_check_handler.evaluate(
        task.model_copy(update={"assertions": [AssertionSpec(kind="status", expected="404")]}),
        _envelope(
            status_code=404, outcome=Outcome.FAILURE, error_type="http_status", body="missing"
        ),
        None,
    )
    assert ok.outcome is Outcome.SUCCESS

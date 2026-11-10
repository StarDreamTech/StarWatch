"""调度表达式。"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from starwatch_core.cron import advance_next, next_occurrence, parse_schedule
from starwatch_core.errors import ScheduleError
from starwatch_core.schemas import ScheduleKind


@pytest.mark.parametrize(
    ("expression", "seconds"),
    [
        ("every 30s", 30),
        ("every 1 minute", 60),
        ("@every 5m", 300),
        ("2 hours", 7200),
        ("每 2 小时", 7200),
        ("每30秒", 30),
    ],
)
def test_interval_shorthand(expression: str, seconds: int) -> None:
    """间隔写法解析成秒。"""
    parsed = parse_schedule(expression)
    assert parsed.kind is ScheduleKind.INTERVAL
    assert parsed.interval_seconds == seconds


def test_five_field_cron() -> None:
    """标准 5 位 cron 可以通过。"""
    parsed = parse_schedule("*/5 * * * *")
    assert parsed.kind is ScheduleKind.CRON
    assert parsed.interval_seconds is None


@pytest.mark.parametrize("expression", ["", "not a cron", "* * * * * *", "every 1 second"])
def test_rejects_bad_expressions(expression: str) -> None:
    """空表达式、6 位 cron 和过短间隔都被拒绝。"""
    with pytest.raises(ScheduleError):
        parse_schedule(expression)


def test_next_interval_skips_missed_ticks() -> None:
    """错过的节拍不会补跑。"""
    schedule = parse_schedule("every 30s").as_schedule()
    start = datetime(2026, 1, 1, tzinfo=UTC)
    assert next_occurrence(schedule, start) == start + timedelta(seconds=30)
    now = start + timedelta(minutes=5)
    upcoming = advance_next(schedule, start, now)
    assert upcoming > now
    assert (upcoming - now).total_seconds() <= 30

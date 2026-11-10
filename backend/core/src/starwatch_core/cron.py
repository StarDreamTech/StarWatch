"""解析 5 位 cron 以及「every 30s / 每 1 分钟」这类间隔写法。"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from croniter import croniter

from starwatch_core.constants import (
    CHINESE_UNIT_SECONDS,
    CRON_FIELD_COUNT,
    HOUR_UNITS,
    MAX_INTERVAL_SECONDS,
    MAX_SCHEDULE_CATCHUP,
    MIN_INTERVAL_SECONDS,
    MINUTE_UNITS,
    SECOND_UNITS,
    SECONDS_PER_HOUR,
    SECONDS_PER_MINUTE,
)
from starwatch_core.errors import ScheduleError
from starwatch_core.schemas import Schedule, ScheduleKind

_INTERVAL = re.compile(
    r"^(?:every\s+|@every\s+)?(\d+)\s*([a-z]+)$",
    re.IGNORECASE,
)
_CHINESE_INTERVAL = re.compile(r"^每\s*(\d+)\s*(秒|分钟|分|小时|时)$")


@dataclass(frozen=True, slots=True)
class ParsedSchedule:
    """解析结果。interval_seconds 只在间隔调度时有值。"""

    kind: ScheduleKind
    expression: str
    interval_seconds: int | None

    def as_schedule(self) -> Schedule:
        """转换成可持久化的调度模型。"""
        return Schedule(
            kind=self.kind,
            expression=self.expression,
            interval_seconds=self.interval_seconds,
        )


def utcnow() -> datetime:
    """返回带 UTC 时区的当前时间。"""
    return datetime.now(UTC)


def parse_schedule(expression: str) -> ParsedSchedule:
    """解析调度表达式。

    Args:
        expression: 标准 5 位 cron，或 ``every 30s``、``每 1 分钟`` 这类间隔。

    Returns:
        归一化后的调度。

    Raises:
        ScheduleError: 表达式为空、间隔越界，或不是受支持的格式。
    """
    text = expression.strip()
    if not text:
        raise ScheduleError("调度表达式不能为空")
    interval = _interval_seconds(text)
    if interval is not None:
        if interval < MIN_INTERVAL_SECONDS or interval > MAX_INTERVAL_SECONDS:
            raise ScheduleError(
                f"间隔需要在 {MIN_INTERVAL_SECONDS} 秒到 {MAX_INTERVAL_SECONDS} 秒之间"
            )
        return ParsedSchedule(
            kind=ScheduleKind.INTERVAL,
            expression=text,
            interval_seconds=interval,
        )
    fields = text.split()
    if len(fields) != CRON_FIELD_COUNT or not croniter.is_valid(text):
        raise ScheduleError("请使用 5 位 cron（分 时 日 月 周），或写成 every 30s / 每 1 分钟")
    return ParsedSchedule(kind=ScheduleKind.CRON, expression=text, interval_seconds=None)


def next_occurrence(schedule: Schedule, after: datetime) -> datetime:
    """计算 after 之后的下一次触发时间。

    Args:
        schedule: 已解析的调度。
        after: 不含本次的起点，必须带时区。

    Returns:
        下一次触发时间。
    """
    moment = _aware(after)
    if schedule.kind is ScheduleKind.INTERVAL:
        if schedule.interval_seconds is None:
            raise ScheduleError("间隔调度缺少秒数")
        return moment + timedelta(seconds=schedule.interval_seconds)
    iterator = croniter(schedule.expression, moment)
    upcoming = iterator.get_next(datetime)
    if not isinstance(upcoming, datetime):
        raise ScheduleError("cron 表达式没有算出下一次时间")
    return _aware(upcoming)


def advance_next(schedule: Schedule, previous_due: datetime, now: datetime) -> datetime:
    """把下一次触发推进到 now 之后，跳过已经错过的节拍。

    监控任务不做补跑，避免停机后一次性打出大量请求。
    """
    nxt = next_occurrence(schedule, previous_due)
    current = _aware(now)
    steps = 0
    while nxt <= current:
        nxt = next_occurrence(schedule, nxt)
        steps += 1
        if steps >= MAX_SCHEDULE_CATCHUP:
            return next_occurrence(schedule, current)
    return nxt


def _interval_seconds(text: str) -> int | None:
    """识别间隔写法。无法识别时返回 None，交给 cron 解析。"""
    chinese = _CHINESE_INTERVAL.match(text)
    if chinese:
        amount = int(chinese.group(1))
        unit = chinese.group(2)
        return amount * CHINESE_UNIT_SECONDS[unit]
    matched = _INTERVAL.match(text)
    if matched is None:
        return None
    amount = int(matched.group(1))
    unit = matched.group(2).lower()
    if unit in SECOND_UNITS:
        return amount
    if unit in MINUTE_UNITS:
        return amount * SECONDS_PER_MINUTE
    if unit in HOUR_UNITS:
        return amount * SECONDS_PER_HOUR
    return None


def _aware(value: datetime) -> datetime:
    """把缺少时区的时间视为 UTC。"""
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)

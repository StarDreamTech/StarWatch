"""在 Pydantic 模型和 Mongo 文档之间转换。可查询的时间字段保留为 datetime。"""

from __future__ import annotations

from datetime import UTC, datetime, tzinfo
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel

from starwatch_core.schemas import Notification, Run, Snapshot, Task

TASK_DATES = ("next_run_at", "last_run_at", "created_at", "updated_at")
RUN_DATES = ("started_at", "finished_at", "created_at")
NOTE_DATES = ("created_at",)
SNAPSHOT_DATES = ("updated_at",)


def dump_task(task: Task) -> dict[str, Any]:
    """把任务写成文档。_id 与 id 相同。"""
    return _dump(task, TASK_DATES)


def load_task(document: dict[str, Any]) -> Task:
    """从文档恢复任务。"""
    return Task.model_validate(_load_payload(document))


def dump_run(run: Run) -> dict[str, Any]:
    """把运行记录写成文档。"""
    return _dump(run, RUN_DATES)


def load_run(document: dict[str, Any]) -> Run:
    """从文档恢复运行记录。"""
    return Run.model_validate(_load_payload(document))


def dump_notification(item: Notification) -> dict[str, Any]:
    """把通知写成文档。"""
    return _dump(item, NOTE_DATES)


def load_notification(document: dict[str, Any]) -> Notification:
    """从文档恢复通知。"""
    return Notification.model_validate(_load_payload(document))


def dump_snapshot(snapshot: Snapshot) -> dict[str, Any]:
    """把快照写成文档。_id 使用 task_id。"""
    data = _dump(snapshot, SNAPSHOT_DATES, id_field="task_id")
    return data


def load_snapshot(document: dict[str, Any]) -> Snapshot:
    """从文档恢复快照。"""
    return Snapshot.model_validate(_load_payload(document))


def start_of_local_day(now: datetime, timezone_name: str) -> datetime:
    """返回当地自然日的起点，并转换回 UTC。

    Args:
        now: 当前时间。
        timezone_name: IANA 时区名。无法识别时使用 UTC。
    """
    zone: tzinfo
    try:
        zone = ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError:
        zone = UTC
    local = now.astimezone(zone)
    start = local.replace(hour=0, minute=0, second=0, microsecond=0)
    return start.astimezone(UTC)


def _dump(model: BaseModel, date_fields: tuple[str, ...], id_field: str = "id") -> dict[str, Any]:
    """序列化模型，并把指定字段从 ISO 字符串转回 datetime。"""
    data = model.model_dump(mode="json")
    data["_id"] = data[id_field]
    for key in date_fields:
        value = data.get(key)
        if isinstance(value, str):
            data[key] = datetime.fromisoformat(value)
    return data


def _load_payload(document: dict[str, Any]) -> dict[str, Any]:
    """去掉 Mongo 的 _id，其余交给模型校验。"""
    return {key: value for key, value in document.items() if key != "_id"}

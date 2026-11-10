"""把运行结果写成应用内通知，并按配置调用外部通知器。"""

from __future__ import annotations

import logging
from typing import Any, cast
from uuid import uuid4

from starwatch_core.bootstrap import notifiers, register_builtins
from starwatch_core.cron import utcnow
from starwatch_core.errors import PluginNotFoundError
from starwatch_core.notifiers import Delivery, Event
from starwatch_core.protocols import Notifier
from starwatch_core.schemas import Notification, Run, Task, TaskEvaluation
from starwatch_scheduler.repository import TaskRepository

logger = logging.getLogger(__name__)


class NotifyService:
    """通知失败不会回滚已经保存的运行记录。"""

    def __init__(self, repo: TaskRepository) -> None:
        """绑定存储。"""
        self._repo = repo

    async def dispatch(self, task: Task, run: Run, evaluation: TaskEvaluation) -> None:
        """写入一条通知，并尝试外部投递。

        Args:
            task: 触发通知的任务。
            run: 已保存的运行记录。
            evaluation: 任务类型插件的判定。
        """
        if not evaluation.notify or evaluation.notify_category is None:
            return
        if evaluation.notify_category not in task.notify.on:
            return
        register_builtins()
        event = Event(
            title=f"星哨 · {task.name}",
            message=evaluation.summary,
            category=evaluation.notify_category,
            payload={
                "task_id": task.id,
                "task_name": task.name,
                "run_id": run.id,
                "task_type": task.task_type.value,
                "outcome": evaluation.outcome.value,
                "finished_at": run.finished_at.isoformat(),
            },
        )
        delivery = await _deliver(task, event)
        note = Notification(
            id=str(uuid4()),
            task_id=task.id,
            task_name=task.name,
            run_id=run.id,
            category=evaluation.notify_category,
            outcome=evaluation.outcome,
            title=event.title,
            message=event.message,
            provider=task.notify.provider,
            delivery=_delivery_status(delivery.status),
            delivery_detail=delivery.detail,
            created_at=utcnow(),
        )
        try:
            await self._repo.insert_notification(note)
        except Exception:
            logger.exception("写入通知失败 task=%s", task.id)


async def _deliver(task: Task, event: Event) -> Delivery:
    """调用外部通知器。异常留在投递状态里。"""
    try:
        notifier = cast(Notifier, notifiers.get(task.notify.provider))
        result = await notifier.send(event, task.notify.params)
    except PluginNotFoundError as exc:
        return Delivery(status="failed", detail=exc.message)
    except Exception as exc:
        logger.exception("通知器 %s 失败", task.notify.provider)
        return Delivery(status="failed", detail=str(exc) or "通知失败")
    return Delivery(status=str(result.status), detail=result.detail)


def _delivery_status(status: str) -> Any:
    """把通知器返回的状态收成模型接受的字面量。"""
    if status in {"sent", "skipped", "failed", "not_implemented"}:
        return status
    return "failed"

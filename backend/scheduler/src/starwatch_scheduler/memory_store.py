"""内存存储，供测试和没有数据库时的流程验证使用。生产路径使用 MongoDB。"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
from uuid import uuid4

from starwatch_core.constants import PROBLEM_OUTCOME_VALUES, STALE_LOCK_SECONDS
from starwatch_core.cron import advance_next
from starwatch_core.schemas import Notification, Outcome, Run, Snapshot, Stats, Task


class MemoryRepository:
    """把文档放在进程内字典里，语义与 Mongo 实现对齐。"""

    def __init__(self) -> None:
        """创建空存储。"""
        self._tasks: dict[str, Task] = {}
        self._runs: dict[str, Run] = {}
        self._snapshots: dict[str, Snapshot] = {}
        self._notifications: dict[str, Notification] = {}
        self._lock = asyncio.Lock()

    async def setup(self) -> None:
        """内存存储没有连接步骤。"""

    async def close(self) -> None:
        """内存存储没有连接可关。"""

    async def ping(self) -> bool:
        """内存存储始终可用。"""
        return True

    async def create_task(self, task: Task) -> Task:
        """保存新任务。"""
        async with self._lock:
            self._tasks[task.id] = task
            return task

    async def save_task(self, task: Task) -> Task:
        """替换任务。"""
        async with self._lock:
            self._tasks[task.id] = task
            return task

    async def get_task(self, task_id: str) -> Task | None:
        """读取任务。"""
        async with self._lock:
            return self._tasks.get(task_id)

    async def delete_task(self, task_id: str) -> bool:
        """删除任务和快照。"""
        async with self._lock:
            existed = self._tasks.pop(task_id, None) is not None
            self._snapshots.pop(task_id, None)
            return existed

    async def list_tasks(
        self,
        *,
        task_type: str | None,
        query: str | None,
        limit: int,
        offset: int,
    ) -> tuple[list[Task], int]:
        """按创建时间倒序分页。"""
        async with self._lock:
            items = [task for task in self._tasks.values() if _task_matches(task, task_type, query)]
            items.sort(key=lambda task: task.created_at, reverse=True)
            return items[offset : offset + limit], len(items)

    async def claim_due(self, now: datetime, limit: int) -> list[Task]:
        """领走到期任务。"""
        async with self._lock:
            due = [task for task in self._tasks.values() if _claimable(task, now)]
            due.sort(key=lambda task: task.next_run_at)
            claimed: list[Task] = []
            for task in due[:limit]:
                token = str(uuid4())
                nxt = advance_next(task.schedule, task.next_run_at, now)
                updated = task.model_copy(
                    update={
                        "running": True,
                        "next_run_at": nxt,
                        "last_run_at": now,
                        "lock_token": token,
                        "updated_at": now,
                    }
                )
                self._tasks[task.id] = updated
                claimed.append(updated)
            return claimed

    async def lock_task(self, task_id: str, now: datetime) -> Task | None:
        """手动运行加锁，不改下一次调度时间。"""
        async with self._lock:
            task = self._tasks.get(task_id)
            if task is None or not _lockable(task, now):
                return None
            updated = task.model_copy(
                update={
                    "running": True,
                    "last_run_at": now,
                    "lock_token": str(uuid4()),
                    "updated_at": now,
                }
            )
            self._tasks[task_id] = updated
            return updated

    async def finish_task(
        self,
        task_id: str,
        outcome: Outcome,
        now: datetime,
        lock_token: str | None,
    ) -> None:
        """释放锁。令牌不一致时保留新的运行标记。"""
        async with self._lock:
            task = self._tasks.get(task_id)
            if task is None:
                return
            if lock_token is not None and task.lock_token != lock_token:
                return
            self._tasks[task_id] = task.model_copy(
                update={
                    "running": False,
                    "lock_token": None,
                    "last_outcome": outcome,
                    "updated_at": now,
                }
            )

    async def insert_run(self, run: Run) -> Run:
        """保存运行记录。"""
        async with self._lock:
            self._runs[run.id] = run
            return run

    async def list_runs(
        self,
        *,
        task_id: str | None,
        outcome: str | None,
        limit: int,
        offset: int,
    ) -> tuple[list[Run], int]:
        """按开始时间倒序分页。"""
        async with self._lock:
            items = [
                run
                for run in self._runs.values()
                if (task_id is None or run.task_id == task_id)
                and (outcome is None or run.outcome.value == outcome)
            ]
            items.sort(key=lambda run: run.started_at, reverse=True)
            return items[offset : offset + limit], len(items)

    async def get_run(self, run_id: str) -> Run | None:
        """读取运行记录。"""
        async with self._lock:
            return self._runs.get(run_id)

    async def get_snapshot(self, task_id: str) -> Snapshot | None:
        """读取快照。"""
        async with self._lock:
            return self._snapshots.get(task_id)

    async def save_snapshot(self, snapshot: Snapshot) -> None:
        """覆盖快照。"""
        async with self._lock:
            self._snapshots[snapshot.task_id] = snapshot

    async def insert_notification(self, item: Notification) -> Notification:
        """保存通知。"""
        async with self._lock:
            self._notifications[item.id] = item
            return item

    async def list_notifications(
        self,
        *,
        limit: int,
        offset: int,
        unread_only: bool,
    ) -> tuple[list[Notification], int]:
        """按时间倒序列出通知。"""
        async with self._lock:
            items = [
                item for item in self._notifications.values() if not unread_only or not item.read
            ]
            items.sort(key=lambda item: item.created_at, reverse=True)
            return items[offset : offset + limit], len(items)

    async def mark_notifications_read(self, ids: list[str] | None) -> int:
        """标记已读。"""
        async with self._lock:
            changed = 0
            for item_id, item in list(self._notifications.items()):
                if item.read:
                    continue
                if ids is not None and item_id not in ids:
                    continue
                self._notifications[item_id] = item.model_copy(update={"read": True})
                changed += 1
            return changed

    async def stats(self, day_start: datetime) -> Stats:
        """扫描内存文档做总览计数。"""
        async with self._lock:
            tasks = list(self._tasks.values())
            runs = [run for run in self._runs.values() if run.started_at >= day_start]
            return Stats(
                tasks=len(tasks),
                enabled=sum(1 for task in tasks if task.enabled),
                page_change=sum(1 for task in tasks if task.task_type.value == "page_change"),
                api_check=sum(1 for task in tasks if task.task_type.value == "api_check"),
                load_test=sum(1 for task in tasks if task.task_type.value == "load_test"),
                runs_today=len(runs),
                changed_today=sum(1 for run in runs if run.outcome is Outcome.CHANGED),
                problems_today=sum(
                    1 for run in runs if run.outcome.value in PROBLEM_OUTCOME_VALUES
                ),
                unread_notifications=sum(
                    1 for item in self._notifications.values() if not item.read
                ),
            )


def _task_matches(task: Task, task_type: str | None, query: str | None) -> bool:
    """类型和关键字过滤。"""
    if task_type is not None and task.task_type.value != task_type:
        return False
    if not query:
        return True
    haystack = f"{task.name}\n{task.description}\n{task.request.url}".lower()
    return query.lower() in haystack


def _claimable(task: Task, now: datetime) -> bool:
    """到期且没有新鲜的运行锁。"""
    return task.enabled and task.next_run_at <= now and _lockable(task, now)


def _lockable(task: Task, now: datetime) -> bool:
    """没有运行，或锁已经超过回收时间。"""
    if not task.running:
        return True
    if task.last_run_at is None:
        return True
    return (now - task.last_run_at) > timedelta(seconds=STALE_LOCK_SECONDS)

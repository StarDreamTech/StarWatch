"""定时领走到期任务。这个循环不直接访问目标网站。"""

from __future__ import annotations

import asyncio
import logging

from starwatch_core.cron import utcnow
from starwatch_core.schemas import Task, TaskType
from starwatch_scheduler.config import Settings
from starwatch_scheduler.executor import execute_task
from starwatch_scheduler.fetcher_client import FetchClient
from starwatch_scheduler.notify_service import NotifyService
from starwatch_scheduler.repository import TaskRepository

logger = logging.getLogger(__name__)


async def scheduler_loop(
    stop: asyncio.Event,
    *,
    repo: TaskRepository,
    fetcher: FetchClient,
    notifier: NotifyService,
    settings: Settings,
) -> None:
    """按轮询间隔领取到期任务。压测单独占用更小的并发名额。

    Args:
        stop: 置位后循环在当前轮次结束后退出。
        repo: 存储。
        fetcher: 抓取客户端。
        notifier: 通知服务。
        settings: 轮询和并发配置。
    """
    general_gate = asyncio.Semaphore(max(1, settings.scheduler_max_concurrency))
    load_gate = asyncio.Semaphore(max(1, settings.scheduler_load_concurrency))
    while not stop.is_set():
        try:
            due = await repo.claim_due(utcnow(), settings.scheduler_batch_size)
            if due:
                async with asyncio.TaskGroup() as group:
                    for task in due:
                        group.create_task(
                            _guarded(task, general_gate, load_gate, repo, fetcher, notifier)
                        )
        except Exception:
            logger.exception("调度循环本轮失败")
        try:
            await asyncio.wait_for(stop.wait(), timeout=settings.scheduler_poll_seconds)
        except TimeoutError:
            continue


async def _guarded(
    task: Task,
    general_gate: asyncio.Semaphore,
    load_gate: asyncio.Semaphore,
    repo: TaskRepository,
    fetcher: FetchClient,
    notifier: NotifyService,
) -> None:
    """按任务类型选择并发闸门。"""
    gate = load_gate if task.task_type is TaskType.LOAD_TEST else general_gate
    async with gate:
        await execute_task(task, repo=repo, fetcher=fetcher, notifier=notifier)

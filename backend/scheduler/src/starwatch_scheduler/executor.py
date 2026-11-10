"""执行一个已经被锁定的任务：调用抓取器、解释结果、入库。"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import cast
from uuid import uuid4

from starwatch_core.bootstrap import register_builtins, task_handlers
from starwatch_core.cron import utcnow
from starwatch_core.errors import ConflictError, FetcherUnavailableError, NotFoundError
from starwatch_core.protocols import TaskHandler
from starwatch_core.schemas import (
    FetchEnvelope,
    FetchRequest,
    Outcome,
    Run,
    Snapshot,
    Task,
    TaskEvaluation,
    TaskType,
)
from starwatch_scheduler.fetcher_client import FetchClient
from starwatch_scheduler.notify_service import NotifyService
from starwatch_scheduler.repository import TaskRepository

logger = logging.getLogger(__name__)


async def execute_task(
    task: Task,
    *,
    repo: TaskRepository,
    fetcher: FetchClient,
    notifier: NotifyService,
) -> Run:
    """执行任务并保证释放锁。

    Args:
        task: 已经带有 lock_token 的任务快照。
        repo: 存储。
        fetcher: 抓取客户端。
        notifier: 通知服务。

    Returns:
        写入后的运行记录。意外异常也会尽量落成一条失败记录。
    """
    started = utcnow()
    outcome = Outcome.FAILURE
    run: Run | None = None
    try:
        previous = await _previous_fields(repo, task)
        envelope = await _fetch(fetcher, task)
        register_builtins()
        handler = cast(TaskHandler, task_handlers.get(task.task_type.value))
        evaluation = handler.evaluate(task, envelope, previous)
        finished = utcnow()
        run = _build_run(task, envelope, evaluation, previous, started, finished)
        await repo.insert_run(run)
        if evaluation.snapshot is not None:
            await repo.save_snapshot(
                Snapshot(task_id=task.id, fields=evaluation.snapshot, updated_at=finished)
            )
        outcome = evaluation.outcome
        await notifier.dispatch(task, run, evaluation)
        logger.info("task=%s outcome=%s", task.id, outcome.value)
        return run
    except Exception:
        logger.exception("执行任务失败 task=%s", task.id)
        if run is None:
            run = _crash_run(task, started, utcnow())
            try:
                await repo.insert_run(run)
            except Exception:
                logger.exception("失败记录也无法写入 task=%s", task.id)
        return run
    finally:
        await repo.finish_task(task.id, outcome, utcnow(), task.lock_token)


async def run_manual(
    task_id: str,
    *,
    repo: TaskRepository,
    fetcher: FetchClient,
    notifier: NotifyService,
) -> Run:
    """立即运行一个任务。正在运行时返回冲突。"""
    existing = await repo.get_task(task_id)
    if existing is None:
        raise NotFoundError("任务不存在")
    locked = await repo.lock_task(task_id, utcnow())
    if locked is None:
        raise ConflictError("任务正在运行")
    return await execute_task(locked, repo=repo, fetcher=fetcher, notifier=notifier)


async def _previous_fields(repo: TaskRepository, task: Task) -> dict[str, list[str]] | None:
    """网页监控才需要上一份快照。"""
    if task.task_type is not TaskType.PAGE_CHANGE:
        return None
    snapshot = await repo.get_snapshot(task.id)
    return snapshot.fields if snapshot else None


async def _fetch(fetcher: FetchClient, task: Task) -> FetchEnvelope:
    """调用抓取器。抓取器不可达时变成一条失败结果，而不是丢掉这次调度。"""
    try:
        return await fetcher.fetch(_fetch_request(task))
    except FetcherUnavailableError as exc:
        return FetchEnvelope(
            outcome=Outcome.FAILURE,
            error_type="fetcher_unavailable",
            error_message=exc.message,
            requester=task.requester.name,
            proxy_label=task.proxy.provider,
        )


def _fetch_request(task: Task) -> FetchRequest:
    """组装抓取请求。压测不带提取规则，其它任务不带负载参数。"""
    load = task.load if task.task_type is TaskType.LOAD_TEST else None
    rules = [] if task.task_type is TaskType.LOAD_TEST else task.extract_rules
    return FetchRequest(
        request=task.request,
        requester=task.requester,
        proxy=task.proxy,
        extract_rules=rules,
        load=load,
        task_type=task.task_type,
    )


def _build_run(
    task: Task,
    envelope: FetchEnvelope,
    evaluation: TaskEvaluation,
    previous: dict[str, list[str]] | None,
    started: datetime,
    finished: datetime,
) -> Run:
    """把判定和抓取详情收成运行记录。"""
    return Run(
        id=str(uuid4()),
        task_id=task.id,
        task_name=task.name,
        task_type=task.task_type,
        outcome=evaluation.outcome,
        error_type=evaluation.error_type or envelope.error_type,
        error_message=evaluation.error_message or envelope.error_message,
        summary=evaluation.summary,
        started_at=started,
        finished_at=finished,
        latency_ms=envelope.latency_ms,
        status_code=envelope.status_code,
        final_url=envelope.final_url,
        headers=envelope.headers,
        body=envelope.body,
        body_truncated=envelope.body_truncated,
        extracted=envelope.extracted,
        previous=previous,
        diff=evaluation.diff,
        load=envelope.load,
        requester=envelope.requester,
        proxy_label=envelope.proxy_label,
        created_at=finished,
    )


def _crash_run(task: Task, started: datetime, finished: datetime) -> Run:
    """执行器自身出错时留下的失败记录。"""
    return Run(
        id=str(uuid4()),
        task_id=task.id,
        task_name=task.name,
        task_type=task.task_type,
        outcome=Outcome.FAILURE,
        error_type="internal",
        error_message="调度器执行任务时发生内部错误",
        summary="调度器执行任务时发生内部错误",
        started_at=started,
        finished_at=finished,
        requester=task.requester.name,
        proxy_label=task.proxy.provider,
        created_at=finished,
    )

"""任务配置的校验和增删改查。不在这里发请求。"""

from __future__ import annotations

from datetime import datetime
from typing import cast
from uuid import uuid4

from starwatch_core.bootstrap import (
    extractors,
    notifiers,
    proxies,
    register_builtins,
    requesters,
    task_handlers,
)
from starwatch_core.cron import next_occurrence, parse_schedule, utcnow
from starwatch_core.errors import NotFoundError, StarWatchError
from starwatch_core.protocols import Extractor, ProxyProvider
from starwatch_core.schemas import Schedule, Task, TaskCreate, TaskType
from starwatch_scheduler.repository import TaskRepository


class TaskService:
    """任务用例。插件是否存在在保存时就检查。"""

    def __init__(self, repo: TaskRepository) -> None:
        """绑定存储。"""
        self._repo = repo

    async def create_task(self, body: TaskCreate) -> Task:
        """校验并创建任务。下一次运行时间从现在开始算。"""
        schedule = _validated_schedule(body)
        now = utcnow()
        task = _new_task(body, schedule, now, str(uuid4()))
        return await self._repo.create_task(task)

    async def replace_task(self, task_id: str, body: TaskCreate) -> Task:
        """替换配置。调度表达式没变时保留原来的下次运行时间。"""
        existing = await self._require(task_id)
        schedule = _validated_schedule(body)
        now = utcnow()
        next_run = existing.next_run_at
        if (
            schedule.expression != existing.schedule.expression
            or schedule.kind != existing.schedule.kind
        ):
            next_run = next_occurrence(schedule, now)
        task = existing.model_copy(
            update={
                "name": body.name,
                "description": body.description,
                "enabled": body.enabled,
                "schedule": schedule,
                "task_type": body.task_type,
                "request": body.request,
                "requester": body.requester,
                "proxy": body.proxy,
                "extract_rules": body.extract_rules,
                "assertions": body.assertions,
                "load": body.load,
                "notify": body.notify,
                "next_run_at": next_run,
                "updated_at": now,
            }
        )
        return await self._repo.save_task(task)

    async def set_enabled(self, task_id: str, enabled: bool) -> Task:
        """只切换启用状态。"""
        existing = await self._require(task_id)
        updated = existing.model_copy(update={"enabled": enabled, "updated_at": utcnow()})
        return await self._repo.save_task(updated)

    async def get_task(self, task_id: str) -> Task:
        """读取任务。不存在时抛出 NotFoundError。"""
        return await self._require(task_id)

    async def delete_task(self, task_id: str) -> None:
        """删除任务。"""
        if not await self._repo.delete_task(task_id):
            raise NotFoundError("任务不存在")

    async def list_tasks(
        self,
        *,
        task_type: str | None,
        query: str | None,
        limit: int,
        offset: int,
    ) -> tuple[list[Task], int]:
        """列出任务。"""
        _check_task_type(task_type)
        return await self._repo.list_tasks(
            task_type=task_type, query=query, limit=limit, offset=offset
        )

    async def _require(self, task_id: str) -> Task:
        """读取任务，缺失时抛 404。"""
        task = await self._repo.get_task(task_id)
        if task is None:
            raise NotFoundError("任务不存在")
        return task


def _validated_schedule(body: TaskCreate) -> Schedule:
    """检查插件、提取规则和调度表达式。"""
    register_builtins()
    schedule = parse_schedule(body.schedule).as_schedule()
    requesters.get(body.requester.name)
    provider = cast(ProxyProvider, proxies.get(body.proxy.provider))
    provider.validate(body.proxy.params)
    notifiers.get(body.notify.provider)
    task_handlers.get(body.task_type.value)
    names: list[str] = []
    for rule in body.extract_rules:
        if rule.name in names:
            raise StarWatchError("invalid_task", f"提取字段重名：{rule.name}", status_code=422)
        names.append(rule.name)
        cast(Extractor, extractors.get(rule.kind)).validate(rule)
    if body.task_type is TaskType.PAGE_CHANGE and not body.extract_rules:
        raise StarWatchError("invalid_task", "网页监控至少需要一条提取规则", status_code=422)
    if body.task_type is TaskType.LOAD_TEST and body.load is None:
        raise StarWatchError("invalid_task", "压测任务需要设置并发和停止条件", status_code=422)
    if body.task_type is not TaskType.LOAD_TEST and body.load is not None:
        raise StarWatchError("invalid_task", "只有压测任务可以设置负载参数", status_code=422)
    return schedule


def _new_task(body: TaskCreate, schedule: Schedule, now: datetime, task_id: str) -> Task:
    """用已校验的调度组装新任务。"""
    return Task(
        id=task_id,
        name=body.name,
        description=body.description,
        enabled=body.enabled,
        schedule=schedule,
        task_type=body.task_type,
        request=body.request,
        requester=body.requester,
        proxy=body.proxy,
        extract_rules=body.extract_rules,
        assertions=body.assertions,
        load=body.load,
        notify=body.notify,
        next_run_at=next_occurrence(schedule, now),
        created_at=now,
        updated_at=now,
    )


def _check_task_type(task_type: str | None) -> None:
    """拒绝无法识别的任务类型过滤。"""
    if task_type is None:
        return
    try:
        TaskType(task_type)
    except ValueError as exc:
        raise StarWatchError("invalid_task_type", "未知的任务类型", status_code=422) from exc

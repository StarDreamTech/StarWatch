"""任务的增删改查和手动运行。"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Query, Request

from starwatch_core.constants import DEFAULT_PAGE_LIMIT, MAX_PAGE_LIMIT
from starwatch_core.schemas import Page, Run, Task, TaskCreate, TaskPatch
from starwatch_scheduler.config import SEARCH_MAX_LENGTH
from starwatch_scheduler.executor import run_manual
from starwatch_scheduler.task_service import TaskService

router = APIRouter(prefix="/tasks", tags=["tasks"])


def _tasks(request: Request) -> TaskService:
    """从应用状态取出任务服务。"""
    service: TaskService = request.app.state.tasks
    return service


@router.get("", response_model=Page[Task])
async def list_tasks(
    request: Request,
    task_type: Annotated[str | None, Query()] = None,
    q: Annotated[str | None, Query(max_length=SEARCH_MAX_LENGTH)] = None,
    limit: Annotated[int, Query(ge=1, le=MAX_PAGE_LIMIT)] = DEFAULT_PAGE_LIMIT,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> Page[Task]:
    """分页列出任务，可按类型和关键字过滤。"""
    items, total = await _tasks(request).list_tasks(
        task_type=task_type,
        query=q,
        limit=limit,
        offset=offset,
    )
    return Page(items=items, total=total, limit=limit, offset=offset)


@router.post("", response_model=Task, status_code=201)
async def create_task(body: TaskCreate, request: Request) -> Task:
    """创建任务。"""
    return await _tasks(request).create_task(body)


@router.get("/{task_id}", response_model=Task)
async def get_task(task_id: str, request: Request) -> Task:
    """读取一个任务。"""
    return await _tasks(request).get_task(task_id)


@router.put("/{task_id}", response_model=Task)
async def replace_task(task_id: str, body: TaskCreate, request: Request) -> Task:
    """整体替换任务配置。"""
    return await _tasks(request).replace_task(task_id, body)


@router.patch("/{task_id}", response_model=Task)
async def patch_task(task_id: str, body: TaskPatch, request: Request) -> Task:
    """切换任务启用状态。"""
    return await _tasks(request).set_enabled(task_id, body.enabled)


@router.delete("/{task_id}", status_code=204)
async def delete_task(task_id: str, request: Request) -> None:
    """删除任务。历史运行记录会保留。"""
    await _tasks(request).delete_task(task_id)


@router.post("/{task_id}/run", response_model=Run)
async def run_task(task_id: str, request: Request) -> Run:
    """立即运行任务。压测会占用调度器的压测并发名额之外的这次手动调用。"""
    return await run_manual(
        task_id,
        repo=request.app.state.repo,
        fetcher=request.app.state.fetcher,
        notifier=request.app.state.notifier,
    )

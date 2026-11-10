"""运行记录查询。"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Query, Request

from starwatch_core.constants import DEFAULT_PAGE_LIMIT, MAX_PAGE_LIMIT
from starwatch_core.errors import NotFoundError, StarWatchError
from starwatch_core.schemas import Outcome, Page, Run, RunSummary, summarize_run
from starwatch_scheduler.repository import TaskRepository

router = APIRouter(prefix="/runs", tags=["runs"])


def _repo(request: Request) -> TaskRepository:
    """从应用状态取出存储。"""
    repo: TaskRepository = request.app.state.repo
    return repo


@router.get("", response_model=Page[RunSummary])
async def list_runs(
    request: Request,
    task_id: Annotated[str | None, Query()] = None,
    outcome: Annotated[str | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=MAX_PAGE_LIMIT)] = DEFAULT_PAGE_LIMIT,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> Page[RunSummary]:
    """分页列出运行记录。列表不返回正文。"""
    if outcome is not None:
        try:
            Outcome(outcome)
        except ValueError as exc:
            raise StarWatchError("invalid_outcome", "未知的运行结果", status_code=422) from exc
    items, total = await _repo(request).list_runs(
        task_id=task_id,
        outcome=outcome,
        limit=limit,
        offset=offset,
    )
    return Page(
        items=[summarize_run(item) for item in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/{run_id}", response_model=Run)
async def get_run(run_id: str, request: Request) -> Run:
    """读取一条运行记录，包含正文、差异和压测汇总。"""
    run = await _repo(request).get_run(run_id)
    if run is None:
        raise NotFoundError("运行记录不存在")
    return run

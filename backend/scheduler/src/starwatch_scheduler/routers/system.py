"""健康检查、插件目录、总览和通知。"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Query, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field

from starwatch_core.bootstrap import plugin_catalog
from starwatch_core.constants import DEFAULT_PAGE_LIMIT, MAX_PAGE_LIMIT
from starwatch_core.cron import utcnow
from starwatch_core.schemas import Health, Notification, Page, PluginInfo, Stats
from starwatch_scheduler.documents import start_of_local_day
from starwatch_scheduler.repository import TaskRepository

router = APIRouter(tags=["system"])


class ReadNotifications(BaseModel):
    """标记已读。ids 为空时表示全部未读。"""

    model_config = ConfigDict(extra="forbid")
    ids: list[str] | None = None


class ReadResult(BaseModel):
    """标记已读的条数。"""

    model_config = ConfigDict(extra="forbid")
    updated: int = Field(ge=0)


def _repo(request: Request) -> TaskRepository:
    """从应用状态取出存储。"""
    repo: TaskRepository = request.app.state.repo
    return repo


@router.get("/health", response_model=Health)
async def health(request: Request) -> Health | JSONResponse:
    """检查调度器和数据库。内存试验不把存储报成 MongoDB。"""
    settings = request.app.state.settings
    storage_ok = await _repo(request).ping()
    mongo = "skipped" if settings.repository_backend == "memory" else "ok" if storage_ok else "down"
    body = Health(
        status="ok" if storage_ok else "degraded",
        service="scheduler",
        mongo=mongo,
    )
    if not storage_ok:
        return JSONResponse(status_code=503, content=body.model_dump())
    return body


@router.get("/plugins", response_model=list[PluginInfo])
async def plugins() -> list[PluginInfo]:
    """列出全部插件槽位。"""
    return plugin_catalog()


@router.get("/stats", response_model=Stats)
async def stats(request: Request) -> Stats:
    """总览计数。自然日按配置的时区计算。"""
    settings = request.app.state.settings
    return await _repo(request).stats(start_of_local_day(utcnow(), settings.app_timezone))


@router.get("/notifications", response_model=Page[Notification])
async def list_notifications(
    request: Request,
    unread_only: Annotated[bool, Query()] = False,
    limit: Annotated[int, Query(ge=1, le=MAX_PAGE_LIMIT)] = DEFAULT_PAGE_LIMIT,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> Page[Notification]:
    """分页列出应用内通知。"""
    items, total = await _repo(request).list_notifications(
        limit=limit,
        offset=offset,
        unread_only=unread_only,
    )
    return Page(items=items, total=total, limit=limit, offset=offset)


@router.post("/notifications/read", response_model=ReadResult)
async def mark_read(body: ReadNotifications, request: Request) -> ReadResult:
    """把通知标为已读。"""
    updated = await _repo(request).mark_notifications_read(body.ids)
    return ReadResult(updated=updated)

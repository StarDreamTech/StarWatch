"""调度服务的 FastAPI 入口。"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager, suppress

import uvicorn
from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from starwatch_core.bootstrap import load_entry_points, register_builtins
from starwatch_core.errors import StarWatchError
from starwatch_core.ratelimit import RateLimiter
from starwatch_core.schemas import Health
from starwatch_scheduler.config import Settings, get_settings
from starwatch_scheduler.fetcher_client import FetchClient, HttpxFetchClient
from starwatch_scheduler.logging import configure_logging
from starwatch_scheduler.loop import scheduler_loop
from starwatch_scheduler.memory_store import MemoryRepository
from starwatch_scheduler.mongo_store import MongoRepository
from starwatch_scheduler.notify_service import NotifyService
from starwatch_scheduler.repository import TaskRepository
from starwatch_scheduler.routers import runs, system, tasks
from starwatch_scheduler.task_service import TaskService

_SKIP_LIMIT = frozenset({"/health", "/api/health", "/docs", "/openapi.json", "/redoc"})
RequestResponse = Callable[[Request], Awaitable[Response]]


class RateLimitMiddleware(BaseHTTPMiddleware):
    """按来源地址限制 API 调用频率。"""

    async def dispatch(self, request: Request, call_next: RequestResponse) -> Response:
        """跳过预检和健康检查。"""
        if request.method == "OPTIONS" or request.url.path in _SKIP_LIMIT:
            return await call_next(request)
        limiter: RateLimiter = request.app.state.limiter
        host = request.client.host if request.client else "unknown"
        if not await limiter.allow(host):
            return JSONResponse(
                status_code=429,
                content={"code": "rate_limited", "message": "请求过于频繁", "details": {}},
            )
        return await call_next(request)


def create_app(
    settings: Settings | None = None,
    repo: TaskRepository | None = None,
    fetcher: FetchClient | None = None,
) -> FastAPI:
    """装配调度服务。

    Args:
        settings: 显式配置。为空时读取环境变量。
        repo: 存储实现。为空时按 REPOSITORY_BACKEND 选择 MongoDB 或内存。
        fetcher: 抓取客户端。为空时按 FETCHER_BASE_URL 创建。
    """
    settings = settings or get_settings()
    if repo is not None:
        repository = repo
    elif settings.repository_backend == "memory":
        repository = MemoryRepository()
    else:
        repository = MongoRepository(settings.mongodb_uri, settings.mongodb_db)
    fetch_client = fetcher or HttpxFetchClient(
        settings.fetcher_base_url,
        settings.fetcher_timeout_seconds,
    )

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        configure_logging(settings.log_level)
        register_builtins()
        load_entry_points()
        await app.state.repo.setup()
        await app.state.fetcher.open()
        stop = asyncio.Event()
        app.state.stop = stop
        loop_task: asyncio.Task[None] | None = None
        if settings.scheduler_enabled:
            loop_task = asyncio.create_task(
                scheduler_loop(
                    stop,
                    repo=app.state.repo,
                    fetcher=app.state.fetcher,
                    notifier=app.state.notifier,
                    settings=settings,
                )
            )
        try:
            yield
        finally:
            stop.set()
            if loop_task is not None:
                loop_task.cancel()
                with suppress(asyncio.CancelledError):
                    await loop_task
            await app.state.fetcher.close()
            await app.state.repo.close()

    app = FastAPI(title="星哨调度器", version="0.1.0", lifespan=lifespan)
    app.state.settings = settings
    app.state.repo = repository
    app.state.fetcher = fetch_client
    app.state.notifier = NotifyService(repository)
    app.state.tasks = TaskService(repository)
    app.state.limiter = RateLimiter(
        settings.rate_limit_requests, settings.rate_limit_window_seconds
    )
    app.add_middleware(RateLimitMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=False,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "Accept"],
    )
    _install_handlers(app)
    app.include_router(system.router, prefix="/api")
    app.include_router(tasks.router, prefix="/api")
    app.include_router(runs.router, prefix="/api")

    @app.get("/health", response_model=Health)
    async def root_health(request: Request) -> Health | JSONResponse:
        """容器探针使用的健康检查。"""
        return await system.health(request)

    return app


def _install_handlers(app: FastAPI) -> None:
    """统一错误体。"""

    @app.exception_handler(StarWatchError)
    async def handle_starwatch(_request: Request, exc: StarWatchError) -> JSONResponse:
        return JSONResponse(status_code=exc.status_code, content=exc.to_body())

    @app.exception_handler(RequestValidationError)
    async def handle_validation(_request: Request, exc: RequestValidationError) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content={
                "code": "validation_error",
                "message": "请求参数不正确",
                "details": {"errors": jsonable_encoder(exc.errors())},
            },
        )


app = create_app()


def run() -> None:
    """用配置里的地址启动调度器。"""
    settings = get_settings()
    uvicorn.run(
        "starwatch_scheduler.main:app",
        host=settings.scheduler_host,
        port=settings.scheduler_port,
        log_level=settings.log_level.lower(),
    )

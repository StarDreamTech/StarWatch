"""抓取服务的 FastAPI 入口。"""

from __future__ import annotations

from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from starwatch_core.bootstrap import load_entry_points, plugin_catalog, register_builtins
from starwatch_core.errors import StarWatchError
from starwatch_core.ratelimit import RateLimiter
from starwatch_core.schemas import FetchEnvelope, FetchRequest, Health, PluginInfo
from starwatch_fetcher.config import Settings, get_settings
from starwatch_fetcher.service import FetchService

_SKIP_LIMIT = frozenset({"/health", "/docs", "/openapi.json", "/redoc"})
RequestResponse = Callable[[Request], Awaitable[Response]]


class RateLimitMiddleware(BaseHTTPMiddleware):
    """按客户端地址限制抓取接口的调用频率。"""

    async def dispatch(self, request: Request, call_next: RequestResponse) -> Response:
        """放行预检和健康检查，其余请求计入窗口。"""
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


def create_app(settings: Settings | None = None, service: FetchService | None = None) -> FastAPI:
    """装配抓取服务。

    Args:
        settings: 显式配置。为空时读取环境变量。
        service: 可替换的抓取实现，测试会传入替身。
    """
    settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        register_builtins()
        load_entry_points()
        yield
        del app

    app = FastAPI(title="星哨抓取器", version="0.1.0", lifespan=lifespan)
    app.state.settings = settings
    app.state.service = service or FetchService()
    app.state.limiter = RateLimiter(
        settings.rate_limit_requests, settings.rate_limit_window_seconds
    )
    app.add_middleware(RateLimitMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=False,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "Accept"],
    )
    _install_handlers(app)

    @app.get("/health", response_model=Health)
    async def health() -> Health:
        """抓取器自身健康检查。"""
        return Health(status="ok", service="fetcher", mongo="skipped")

    @app.get("/plugins", response_model=list[PluginInfo])
    async def plugins() -> list[PluginInfo]:
        """列出请求器和代理槽位。"""
        return [
            item for item in plugin_catalog() if item.slot in {"requester", "proxy", "extractor"}
        ]

    @app.post("/fetch", response_model=FetchEnvelope)
    async def fetch(payload: FetchRequest, request: Request) -> FetchEnvelope:
        """执行一次抓取或压测并返回归一化结果。"""
        service_impl: FetchService = request.app.state.service
        return await service_impl.execute(payload)

    return app


def _install_handlers(app: FastAPI) -> None:
    """把领域异常和参数错误收成同一形状。"""

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
    """用配置里的地址启动抓取器。"""
    settings = get_settings()
    uvicorn.run(
        "starwatch_fetcher.main:app",
        host=settings.fetcher_host,
        port=settings.fetcher_port,
        log_level=settings.log_level.lower(),
    )

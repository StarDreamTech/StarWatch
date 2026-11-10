"""抓取器 HTTP API。"""

from __future__ import annotations

from fastapi.testclient import TestClient

from starwatch_core.classify import RawExchange
from starwatch_core.schemas import Outcome
from starwatch_fetcher.config import Settings
from starwatch_fetcher.main import create_app
from starwatch_fetcher.service import FetchService


def _payload() -> dict[str, object]:
    """最小抓取请求。"""
    return {
        "task_type": "api_check",
        "request": {"url": "https://example.com/health"},
    }


def test_fetch_reports_blocked_and_lists_plugins() -> None:
    """403 走真实分类，插件目录包含 httpx 和存根。"""
    app = create_app(Settings(rate_limit_requests=1000, cors_origins="http://localhost:5173"))

    class Scripted(FetchService):
        async def execute(self, payload):  # type: ignore[no-untyped-def]
            del payload
            from starwatch_fetcher.service import envelope_from_exchange

            return envelope_from_exchange(
                RawExchange(status_code=403, body="nope"),
                {},
                "httpx",
                "direct",
                None,
            )

    app.state.service = Scripted()
    with TestClient(app) as client:
        denied = client.post("/fetch", json=_payload())
        assert denied.status_code == 200
        body = denied.json()
        assert body["outcome"] == Outcome.BLOCKED.value
        assert body["error_type"] == "forbidden"
        plugins = client.get("/plugins")
        assert plugins.status_code == 200
        names = {item["name"] for item in plugins.json()}
        assert "httpx" in names
        assert "pool_api" in names


def test_real_service_marks_unimplemented_requester() -> None:
    """选择尚未实现的请求器时返回失败，而不是空成功。"""
    app = create_app(Settings(rate_limit_requests=1000, cors_origins="http://localhost:5173"))
    with TestClient(app) as client:
        response = client.post(
            "/fetch",
            json={
                **_payload(),
                "requester": {"name": "playwright", "params": {}},
            },
        )
        assert response.status_code == 200
        body = response.json()
        assert body["outcome"] == Outcome.FAILURE.value
        assert body["error_type"] == "requester_unavailable"


def test_rate_limit() -> None:
    """超过窗口后返回 429。"""
    app = create_app(
        Settings(
            rate_limit_requests=2,
            rate_limit_window_seconds=60,
            cors_origins="http://localhost:5173",
        )
    )
    with TestClient(app) as client:
        assert client.get("/health").status_code == 200
        assert client.get("/plugins").status_code == 200
        assert client.get("/plugins").status_code == 200
        blocked = client.get("/plugins")
        assert blocked.status_code == 429
        assert blocked.json()["code"] == "rate_limited"

"""调度器 API、手动运行和结果入库。"""

from __future__ import annotations

from fastapi.testclient import TestClient

from starwatch_core.schemas import FetchEnvelope, FetchRequest, Outcome
from starwatch_scheduler.config import Settings
from starwatch_scheduler.main import create_app
from starwatch_scheduler.memory_store import MemoryRepository


class FakeFetcher:
    """按脚本返回抓取结果，并记住调用次数。"""

    def __init__(self) -> None:
        """从空脚本开始。"""
        self.envelopes: list[FetchEnvelope] = []
        self.calls = 0

    async def open(self) -> None:
        """测试替身没有连接。"""

    async def close(self) -> None:
        """测试替身没有连接。"""

    async def fetch(self, payload: FetchRequest) -> FetchEnvelope:
        """返回下一条脚本结果。"""
        self.calls += 1
        if not self.envelopes:
            raise AssertionError("missing scripted envelope")
        return self.envelopes.pop(0)


def _settings() -> Settings:
    """关闭调度循环，避免测试依赖时间流逝。"""
    return Settings(
        scheduler_enabled=False,
        rate_limit_requests=1000,
        cors_origins="http://localhost:5173",
        mongodb_uri="mongodb://example.invalid:27017",
    )


def _page_task() -> dict[str, object]:
    """一条网页监控任务。"""
    return {
        "name": "示例首页",
        "schedule": "every 1 minute",
        "task_type": "page_change",
        "request": {"url": "https://example.com"},
        "extract_rules": [{"name": "title", "kind": "css", "expression": "h1"}],
    }


def _envelope(
    outcome: Outcome, extracted: dict[str, list[str]] | None = None, **extra: object
) -> FetchEnvelope:
    """脚本化的抓取结果。"""
    return FetchEnvelope(
        outcome=outcome,
        requester="httpx",
        proxy_label="direct",
        status_code=200 if outcome is not Outcome.BLOCKED else 403,
        body="body",
        extracted=extracted or {},
        error_type="forbidden" if outcome is Outcome.BLOCKED else None,
        error_message="目标返回 403" if outcome is Outcome.BLOCKED else None,
        **extra,
    )


def test_task_run_stores_blocked_baseline_and_change() -> None:
    """创建任务后手动运行，拦截、基线和变化都会留下记录。"""
    fetcher = FakeFetcher()
    fetcher.envelopes = [
        _envelope(Outcome.BLOCKED),
        _envelope(Outcome.SUCCESS, {"title": ["甲"]}),
        _envelope(Outcome.SUCCESS, {"title": ["乙"]}),
    ]
    app = create_app(_settings(), repo=MemoryRepository(), fetcher=fetcher)
    with TestClient(app) as client:
        created = client.post("/api/tasks", json=_page_task())
        assert created.status_code == 201
        task_id = created.json()["id"]
        blocked = client.post(f"/api/tasks/{task_id}/run")
        assert blocked.status_code == 200
        assert blocked.json()["outcome"] == "blocked"
        baseline = client.post(f"/api/tasks/{task_id}/run")
        assert baseline.json()["outcome"] == "baseline"
        changed = client.post(f"/api/tasks/{task_id}/run")
        assert changed.json()["outcome"] == "changed"
        assert changed.json()["diff"]["changed"] is True
        listed = client.get("/api/runs", params={"task_id": task_id})
        assert listed.status_code == 200
        assert listed.json()["total"] == 3
        detail = client.get(f"/api/runs/{changed.json()['id']}")
        assert detail.json()["diff"]["fields"][0]["after"] == ["乙"]
        notes = client.get("/api/notifications")
        assert notes.json()["total"] >= 2
        stats = client.get("/api/stats")
        assert stats.json()["page_change"] == 1


def test_validation_and_unknown_plugin() -> None:
    """坏的 cron、未知请求器和静态代理缺参都返回 422。"""
    app = create_app(_settings(), repo=MemoryRepository(), fetcher=FakeFetcher())
    with TestClient(app) as client:
        bad_cron = client.post("/api/tasks", json={**_page_task(), "schedule": "nope"})
        assert bad_cron.status_code == 422
        assert bad_cron.json()["code"] == "invalid_schedule"
        unknown = client.post(
            "/api/tasks",
            json={**_page_task(), "requester": {"name": "does-not-exist", "params": {}}},
        )
        assert unknown.status_code == 422
        assert unknown.json()["code"] == "unknown_plugin"
        proxy = client.post(
            "/api/tasks",
            json={**_page_task(), "proxy": {"provider": "static", "params": {}}},
        )
        assert proxy.status_code == 422
        assert proxy.json()["code"] == "invalid_proxy"
        plugins = client.get("/api/plugins")
        assert any(item["name"] == "webhook" and item["implemented"] for item in plugins.json())


def test_disable_delete_and_cors() -> None:
    """可以停用、删除任务，并且只反射允许的来源。"""
    app = create_app(_settings(), repo=MemoryRepository(), fetcher=FakeFetcher())
    with TestClient(app) as client:
        created = client.post("/api/tasks", json=_page_task())
        task_id = created.json()["id"]
        patched = client.patch(f"/api/tasks/{task_id}", json={"enabled": False})
        assert patched.json()["enabled"] is False
        deleted = client.delete(f"/api/tasks/{task_id}")
        assert deleted.status_code == 204
        missing = client.get(f"/api/tasks/{task_id}")
        assert missing.status_code == 404
        allowed = client.get("/api/stats", headers={"Origin": "http://localhost:5173"})
        assert allowed.headers["access-control-allow-origin"] == "http://localhost:5173"
        denied = client.get("/api/stats", headers={"Origin": "https://evil.example"})
        assert "access-control-allow-origin" not in denied.headers

"""调度器可以选择内存存储，便于没有 MongoDB 时做本地试验。"""

from fastapi.testclient import TestClient

from starwatch_scheduler.config import Settings
from starwatch_scheduler.main import create_app
from starwatch_scheduler.memory_store import MemoryRepository
from starwatch_scheduler.mongo_store import MongoRepository


def test_default_backend_is_mongo() -> None:
    settings = Settings(repository_backend="mongo")
    app = create_app(settings)
    assert isinstance(app.state.repo, MongoRepository)


def test_memory_backend_skips_mongo() -> None:
    settings = Settings(repository_backend="memory", scheduler_enabled=False)
    app = create_app(settings)
    assert isinstance(app.state.repo, MemoryRepository)
    with TestClient(app) as client:
        response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["mongo"] == "skipped"

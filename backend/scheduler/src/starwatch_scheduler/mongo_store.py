"""PyMongo 异步客户端上的任务存储。"""

from __future__ import annotations

import re
from datetime import datetime, timedelta
from typing import Any
from uuid import uuid4

from pymongo import AsyncMongoClient, ReturnDocument

from starwatch_core.constants import PROBLEM_OUTCOME_VALUES, STALE_LOCK_SECONDS
from starwatch_core.cron import advance_next
from starwatch_core.schemas import Notification, Outcome, Run, Snapshot, Stats, Task
from starwatch_scheduler.config import MONGO_SELECTION_TIMEOUT_MS
from starwatch_scheduler.documents import (
    dump_notification,
    dump_run,
    dump_snapshot,
    dump_task,
    load_notification,
    load_run,
    load_snapshot,
    load_task,
)


class MongoRepository:
    """MongoDB 中的 tasks、runs、snapshots、notifications 四个集合。"""

    def __init__(self, uri: str, database: str) -> None:
        """记录连接参数。真正连接发生在 setup。"""
        self._uri = uri
        self._database_name = database
        self._client: AsyncMongoClient[dict[str, Any]] | None = None
        self._tasks: Any = None
        self._runs: Any = None
        self._snapshots: Any = None
        self._notifications: Any = None

    async def setup(self) -> None:
        """连接数据库并确保索引存在。"""
        self._client = AsyncMongoClient(
            self._uri,
            serverSelectionTimeoutMS=MONGO_SELECTION_TIMEOUT_MS,
        )
        database = self._client[self._database_name]
        self._tasks = database["tasks"]
        self._runs = database["runs"]
        self._snapshots = database["snapshots"]
        self._notifications = database["notifications"]
        await self._tasks.create_index("next_run_at")
        await self._tasks.create_index("task_type")
        await self._runs.create_index([("task_id", 1), ("started_at", -1)])
        await self._runs.create_index("started_at")
        await self._notifications.create_index([("read", 1), ("created_at", -1)])
        await self._snapshots.create_index("task_id", unique=True)

    async def close(self) -> None:
        """关闭客户端。"""
        if self._client is not None:
            await self._client.close()
            self._client = None

    async def ping(self) -> bool:
        """执行 ping。失败时返回 False，不抛给健康检查的调用方。"""
        if self._client is None:
            return False
        try:
            await self._client.admin.command("ping")
        except Exception:
            return False
        return True

    async def create_task(self, task: Task) -> Task:
        """插入任务。"""
        await self._tasks.insert_one(dump_task(task))
        return task

    async def save_task(self, task: Task) -> Task:
        """按 id 替换任务文档。"""
        await self._tasks.replace_one({"_id": task.id}, dump_task(task), upsert=True)
        return task

    async def get_task(self, task_id: str) -> Task | None:
        """读取任务。"""
        document = await self._tasks.find_one({"_id": task_id})
        return load_task(document) if document else None

    async def delete_task(self, task_id: str) -> bool:
        """删除任务和快照。"""
        result = await self._tasks.delete_one({"_id": task_id})
        await self._snapshots.delete_one({"_id": task_id})
        return bool(result.deleted_count)

    async def list_tasks(
        self,
        *,
        task_type: str | None,
        query: str | None,
        limit: int,
        offset: int,
    ) -> tuple[list[Task], int]:
        """分页查询任务。"""
        filt = _task_filter(task_type, query)
        total = await self._tasks.count_documents(filt)
        cursor = self._tasks.find(filt).sort("created_at", -1).skip(offset).limit(limit)
        documents = await cursor.to_list(length=limit)
        return [load_task(document) for document in documents], int(total)

    async def claim_due(self, now: datetime, limit: int) -> list[Task]:
        """逐条原子领取到期任务，避免两个循环重复触发。"""
        claimed: list[Task] = []
        stale_before = now - timedelta(seconds=STALE_LOCK_SECONDS)
        for _ in range(limit):
            token = str(uuid4())
            document = await self._tasks.find_one_and_update(
                {
                    "enabled": True,
                    "next_run_at": {"$lte": now},
                    "$or": [
                        {"running": {"$ne": True}},
                        {"last_run_at": {"$lte": stale_before}},
                    ],
                },
                {
                    "$set": {
                        "running": True,
                        "last_run_at": now,
                        "lock_token": token,
                        "updated_at": now,
                    }
                },
                sort=[("next_run_at", 1)],
                return_document=ReturnDocument.AFTER,
            )
            if document is None:
                break
            task = load_task(document)
            nxt = advance_next(task.schedule, task.next_run_at, now)
            await self._tasks.update_one(
                {"_id": task.id, "lock_token": token},
                {"$set": {"next_run_at": nxt}},
            )
            claimed.append(task.model_copy(update={"next_run_at": nxt, "lock_token": token}))
        return claimed

    async def lock_task(self, task_id: str, now: datetime) -> Task | None:
        """手动运行加锁。"""
        token = str(uuid4())
        stale_before = now - timedelta(seconds=STALE_LOCK_SECONDS)
        document = await self._tasks.find_one_and_update(
            {
                "_id": task_id,
                "$or": [
                    {"running": {"$ne": True}},
                    {"last_run_at": {"$lte": stale_before}},
                ],
            },
            {
                "$set": {
                    "running": True,
                    "last_run_at": now,
                    "lock_token": token,
                    "updated_at": now,
                }
            },
            return_document=ReturnDocument.AFTER,
        )
        return load_task(document) if document else None

    async def finish_task(
        self,
        task_id: str,
        outcome: Outcome,
        now: datetime,
        lock_token: str | None,
    ) -> None:
        """只有令牌仍属于这次运行时才释放锁。"""
        filt: dict[str, Any] = {"_id": task_id}
        if lock_token is not None:
            filt["lock_token"] = lock_token
        await self._tasks.update_one(
            filt,
            {
                "$set": {
                    "running": False,
                    "lock_token": None,
                    "last_outcome": outcome.value,
                    "updated_at": now,
                }
            },
        )

    async def insert_run(self, run: Run) -> Run:
        """插入运行记录。"""
        await self._runs.insert_one(dump_run(run))
        return run

    async def list_runs(
        self,
        *,
        task_id: str | None,
        outcome: str | None,
        limit: int,
        offset: int,
    ) -> tuple[list[Run], int]:
        """分页查询运行记录。"""
        filt: dict[str, Any] = {}
        if task_id is not None:
            filt["task_id"] = task_id
        if outcome is not None:
            filt["outcome"] = outcome
        total = await self._runs.count_documents(filt)
        cursor = self._runs.find(filt).sort("started_at", -1).skip(offset).limit(limit)
        documents = await cursor.to_list(length=limit)
        return [load_run(document) for document in documents], int(total)

    async def get_run(self, run_id: str) -> Run | None:
        """读取运行记录。"""
        document = await self._runs.find_one({"_id": run_id})
        return load_run(document) if document else None

    async def get_snapshot(self, task_id: str) -> Snapshot | None:
        """读取快照。"""
        document = await self._snapshots.find_one({"_id": task_id})
        return load_snapshot(document) if document else None

    async def save_snapshot(self, snapshot: Snapshot) -> None:
        """覆盖快照。"""
        await self._snapshots.replace_one(
            {"_id": snapshot.task_id}, dump_snapshot(snapshot), upsert=True
        )

    async def insert_notification(self, item: Notification) -> Notification:
        """插入通知。"""
        await self._notifications.insert_one(dump_notification(item))
        return item

    async def list_notifications(
        self,
        *,
        limit: int,
        offset: int,
        unread_only: bool,
    ) -> tuple[list[Notification], int]:
        """分页查询通知。"""
        filt: dict[str, Any] = {"read": False} if unread_only else {}
        total = await self._notifications.count_documents(filt)
        cursor = self._notifications.find(filt).sort("created_at", -1).skip(offset).limit(limit)
        documents = await cursor.to_list(length=limit)
        return [load_notification(document) for document in documents], int(total)

    async def mark_notifications_read(self, ids: list[str] | None) -> int:
        """标记已读。"""
        filt: dict[str, Any] = {"read": False}
        if ids is not None:
            filt["_id"] = {"$in": ids}
        result = await self._notifications.update_many(filt, {"$set": {"read": True}})
        return int(result.modified_count)

    async def stats(self, day_start: datetime) -> Stats:
        """用计数查询生成总览。"""
        today = {"started_at": {"$gte": day_start}}
        problems = {**today, "outcome": {"$in": sorted(PROBLEM_OUTCOME_VALUES)}}
        return Stats(
            tasks=int(await self._tasks.count_documents({})),
            enabled=int(await self._tasks.count_documents({"enabled": True})),
            page_change=int(await self._tasks.count_documents({"task_type": "page_change"})),
            api_check=int(await self._tasks.count_documents({"task_type": "api_check"})),
            load_test=int(await self._tasks.count_documents({"task_type": "load_test"})),
            runs_today=int(await self._runs.count_documents(today)),
            changed_today=int(await self._runs.count_documents({**today, "outcome": "changed"})),
            problems_today=int(await self._runs.count_documents(problems)),
            unread_notifications=int(await self._notifications.count_documents({"read": False})),
        )


def _task_filter(task_type: str | None, query: str | None) -> dict[str, Any]:
    """构造任务列表过滤条件。用户输入会先转义，避免被当成正则。"""
    filt: dict[str, Any] = {}
    if task_type is not None:
        filt["task_type"] = task_type
    if query:
        pattern = re.escape(query)
        filt["$or"] = [
            {"name": {"$regex": pattern, "$options": "i"}},
            {"description": {"$regex": pattern, "$options": "i"}},
            {"request.url": {"$regex": pattern, "$options": "i"}},
        ]
    return filt

"""存储接口。调度逻辑只依赖这组方法，测试可以使用内存实现。"""

from __future__ import annotations

from datetime import datetime
from typing import Protocol

from starwatch_core.schemas import Notification, Outcome, Run, Snapshot, Stats, Task


class TaskRepository(Protocol):
    """任务、运行、快照和通知的存储。"""

    async def setup(self) -> None:
        """建立连接和索引。"""

    async def close(self) -> None:
        """关闭连接。"""

    async def ping(self) -> bool:
        """存储是否可访问。"""

    async def create_task(self, task: Task) -> Task:
        """插入任务。"""

    async def save_task(self, task: Task) -> Task:
        """整份替换任务配置，保留调用方已经放进模型的运行状态。"""

    async def get_task(self, task_id: str) -> Task | None:
        """按 id 读取任务。"""

    async def delete_task(self, task_id: str) -> bool:
        """删除任务及其快照。运行记录保留。"""

    async def list_tasks(
        self,
        *,
        task_type: str | None,
        query: str | None,
        limit: int,
        offset: int,
    ) -> tuple[list[Task], int]:
        """分页列出任务。"""

    async def claim_due(self, now: datetime, limit: int) -> list[Task]:
        """原子地领走到期任务，并推进 next_run_at。"""

    async def lock_task(self, task_id: str, now: datetime) -> Task | None:
        """为手动运行加锁。任务不存在或正被占用时返回空。"""

    async def finish_task(
        self,
        task_id: str,
        outcome: Outcome,
        now: datetime,
        lock_token: str | None,
    ) -> None:
        """结束一次运行。令牌不匹配时不覆盖更新的锁。"""

    async def insert_run(self, run: Run) -> Run:
        """写入运行记录。"""

    async def list_runs(
        self,
        *,
        task_id: str | None,
        outcome: str | None,
        limit: int,
        offset: int,
    ) -> tuple[list[Run], int]:
        """分页列出运行记录。"""

    async def get_run(self, run_id: str) -> Run | None:
        """读取一条运行记录。"""

    async def get_snapshot(self, task_id: str) -> Snapshot | None:
        """读取网页监控的上一份快照。"""

    async def save_snapshot(self, snapshot: Snapshot) -> None:
        """覆盖保存快照。"""

    async def insert_notification(self, item: Notification) -> Notification:
        """写入通知。"""

    async def list_notifications(
        self,
        *,
        limit: int,
        offset: int,
        unread_only: bool,
    ) -> tuple[list[Notification], int]:
        """分页列出通知。"""

    async def mark_notifications_read(self, ids: list[str] | None) -> int:
        """把指定通知或全部未读标为已读，返回更新条数。"""

    async def stats(self, day_start: datetime) -> Stats:
        """汇总总览数字。"""

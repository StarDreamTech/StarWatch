"""插件槽位的协议。第三方包按这些方法实现即可被注册。"""

from __future__ import annotations

from typing import Any, Protocol

from starwatch_core.classify import ProxyChoice, RawExchange
from starwatch_core.schemas import (
    ExtractRule,
    FetchEnvelope,
    NotifyCategory,
    RequestSpec,
    Task,
    TaskEvaluation,
)


class Requester(Protocol):
    """真正发出请求的后端。任务配置用 name 选择。"""

    name: str
    description: str
    implemented: bool

    async def execute(self, spec: RequestSpec, proxy: ProxyChoice) -> RawExchange:
        """执行一次请求并返回原始交换。"""


class ProxyProvider(Protocol):
    """为一次请求决定代理。返回的 url 为空表示直连。"""

    name: str
    description: str
    implemented: bool

    def validate(self, params: dict[str, object]) -> None:
        """在保存任务时检查参数。"""

    async def resolve(self, params: dict[str, object]) -> ProxyChoice:
        """解析本次要使用的代理。"""


class Extractor(Protocol):
    """从正文中取出一个字段的全部匹配。"""

    name: str
    description: str
    implemented: bool

    def validate(self, rule: ExtractRule) -> None:
        """在保存任务时编译表达式。"""

    def extract(self, body: str, rule: ExtractRule) -> list[str]:
        """执行提取。没有匹配时返回空列表。"""


class NotifyEvent(Protocol):
    """交给通知器的事件。属性只读，以便冻结的数据对象也能满足协议。"""

    @property
    def title(self) -> str:
        """通知标题。"""

    @property
    def message(self) -> str:
        """通知正文。"""

    @property
    def category(self) -> NotifyCategory:
        """通知类别。"""

    @property
    def payload(self) -> dict[str, Any]:
        """随通知发送的结构化字段。"""


class NotifyDelivery(Protocol):
    """通知器的投递结果。"""

    @property
    def status(self) -> str:
        """sent、skipped、failed 或 not_implemented。"""

    @property
    def detail(self) -> str | None:
        """补充说明。"""


class Notifier(Protocol):
    """把事件送到外部通道。应用内记录由调度器单独写入。"""

    name: str
    description: str
    implemented: bool

    async def send(self, event: NotifyEvent, params: dict[str, object]) -> NotifyDelivery:
        """发送一条通知。"""


class TaskHandler(Protocol):
    """把抓取结果解释成任务结果。"""

    name: str
    description: str
    implemented: bool

    def evaluate(
        self,
        task: Task,
        envelope: FetchEnvelope,
        previous: dict[str, list[str]] | None,
    ) -> TaskEvaluation:
        """根据任务类型给出最终结果。"""

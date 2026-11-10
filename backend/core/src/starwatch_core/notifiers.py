"""Webhook 通知，以及邮件通道的存根。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx

from starwatch_core.constants import WEBHOOK_TIMEOUT_SECONDS
from starwatch_core.schemas import NotifyCategory


@dataclass(frozen=True, slots=True)
class Delivery:
    """一次外部投递的结果。"""

    status: str
    detail: str | None = None


@dataclass(frozen=True, slots=True)
class Event:
    """发给通知器的事件。"""

    title: str
    message: str
    category: NotifyCategory
    payload: dict[str, Any]


class NoneNotifier:
    """不向外部发送，只让调度器保留应用内记录。"""

    name = "none"
    description = "不发送外部通知。"
    implemented = True

    async def send(self, event: Event, params: dict[str, Any]) -> Delivery:
        """跳过外部投递。"""
        del event, params
        return Delivery(status="skipped", detail="未配置外部通知")


class WebhookNotifier:
    """把事件 JSON POST 到 params['url']。"""

    name = "webhook"
    description = "HTTP Webhook。参数 url 是接收地址。"
    implemented = True

    def __init__(self, transport: httpx.AsyncBaseTransport | None = None) -> None:
        """创建通知器。

        Args:
            transport: 测试用传输层。
        """
        self._transport = transport

    async def send(self, event: Event, params: dict[str, Any]) -> Delivery:
        """POST 事件载荷。

        Args:
            event: 通知内容。
            params: 至少包含 url。

        Returns:
            sent、failed 之一。网络异常不会向外抛出。
        """
        url = params.get("url")
        if not isinstance(url, str) or not url.strip():
            return Delivery(status="failed", detail="缺少 webhook url")
        body = {
            "title": event.title,
            "message": event.message,
            "category": event.category,
            **event.payload,
        }
        kwargs: dict[str, object] = {"timeout": WEBHOOK_TIMEOUT_SECONDS}
        if self._transport is not None:
            kwargs["transport"] = self._transport
        try:
            async with httpx.AsyncClient(**kwargs) as client:  # type: ignore[arg-type]
                response = await client.post(url, json=body)
        except httpx.HTTPError as exc:
            return Delivery(status="failed", detail=str(exc) or "webhook 请求失败")
        if response.status_code >= HTTP_CLIENT_ERROR:
            return Delivery(status="failed", detail=f"HTTP {response.status_code}")
        return Delivery(status="sent", detail=f"HTTP {response.status_code}")


class EmailNotifier:
    """邮件通道占位。注册后可见，但不会假装已经发出。"""

    name = "email"
    description = "邮件通知（存根）。后续可接入 SMTP。"
    implemented = False

    async def send(self, event: Event, params: dict[str, Any]) -> Delivery:
        """返回未实现，而不是静默成功。"""
        del event, params
        return Delivery(status="not_implemented", detail="邮件通知尚未实现")


HTTP_CLIENT_ERROR = 400

none_notifier = NoneNotifier()
webhook_notifier = WebhookNotifier()
email_notifier = EmailNotifier()


def build_none() -> NoneNotifier:
    """入口点工厂：不通知。"""
    return none_notifier


def build_webhook() -> WebhookNotifier:
    """入口点工厂：Webhook。"""
    return webhook_notifier


def build_email() -> EmailNotifier:
    """入口点工厂：邮件存根。"""
    return email_notifier

"""注册内置插件，并装载第三方入口点。"""

from __future__ import annotations

import logging
from importlib.metadata import entry_points

from starwatch_core.extractors import (
    css_extractor,
    jsonpath_extractor,
    regex_extractor,
    xpath_extractor,
)
from starwatch_core.handlers import api_check_handler, load_test_handler, page_change_handler
from starwatch_core.notifiers import email_notifier, none_notifier, webhook_notifier
from starwatch_core.proxies import direct_proxy, pool_api_proxy, rotating_proxy, static_proxy
from starwatch_core.registry import Described, Registry
from starwatch_core.requesters import (
    curl_cffi_requester,
    drissionpage_requester,
    httpx_requester,
    playwright_requester,
)
from starwatch_core.schemas import PluginInfo

logger = logging.getLogger(__name__)

requesters: Registry[Described] = Registry("请求器")
proxies: Registry[Described] = Registry("代理")
extractors: Registry[Described] = Registry("提取器")
notifiers: Registry[Described] = Registry("通知器")
task_handlers: Registry[Described] = Registry("任务类型")

_ENTRY_POINTS: dict[str, Registry[Described]] = {
    "starwatch.requesters": requesters,
    "starwatch.proxies": proxies,
    "starwatch.extractors": extractors,
    "starwatch.notifiers": notifiers,
    "starwatch.task_handlers": task_handlers,
}
_SLOT_LABELS = {
    "starwatch.requesters": "requester",
    "starwatch.proxies": "proxy",
    "starwatch.extractors": "extractor",
    "starwatch.notifiers": "notifier",
    "starwatch.task_handlers": "task",
}
_READY = False


def register_builtins() -> None:
    """注册仓库自带的实现和存根。重复调用是安全的。"""
    global _READY
    if _READY:
        return
    for requester in (
        httpx_requester,
        playwright_requester,
        curl_cffi_requester,
        drissionpage_requester,
    ):
        requesters.register(requester)
    for proxy in (direct_proxy, static_proxy, rotating_proxy, pool_api_proxy):
        proxies.register(proxy)
    for extractor in (css_extractor, xpath_extractor, jsonpath_extractor, regex_extractor):
        extractors.register(extractor)
    for notifier in (none_notifier, webhook_notifier, email_notifier):
        notifiers.register(notifier)
    for handler in (page_change_handler, api_check_handler, load_test_handler):
        task_handlers.register(handler)
    _READY = True


def load_entry_points() -> None:
    """装载已安装分发包声明的插件。同名内置插件不会被覆盖。"""
    register_builtins()
    for group, registry in _ENTRY_POINTS.items():
        try:
            found = entry_points(group=group)
        except Exception:
            logger.exception("读取插件入口点失败：%s", group)
            continue
        for item in found:
            if registry.contains(item.name):
                continue
            try:
                factory = item.load()
                plugin = factory()
            except Exception:
                logger.exception("加载插件失败：%s", item.name)
                continue
            name = getattr(plugin, "name", "")
            if isinstance(name, str) and registry.contains(name):
                continue
            registry.register(plugin)


def plugin_catalog() -> list[PluginInfo]:
    """返回全部槽位的目录，供 API 和前端展示。"""
    register_builtins()
    rows: list[PluginInfo] = []
    for group, registry in _ENTRY_POINTS.items():
        slot = _SLOT_LABELS[group]
        for item in registry.list():
            rows.append(
                PluginInfo(
                    slot=slot,
                    name=item.name,
                    description=item.description,
                    implemented=bool(item.implemented),
                )
            )
    return rows

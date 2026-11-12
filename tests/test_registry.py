"""插件注册表。"""

from __future__ import annotations

import pytest

from starwatch_core.bootstrap import proxies, requesters
from starwatch_core.errors import PluginNotFoundError, PluginRegistrationError
from starwatch_core.registry import Registry


def test_builtin_slots_are_named() -> None:
    """内置请求器和代理都出现在目录里。"""
    names = {item.name for item in requesters.list()}
    assert {"httpx", "playwright", "curl_cffi", "drissionpage"} <= names
    assert {item.name for item in proxies.list()} >= {"direct", "static", "rotating", "pool_api"}
    assert requesters.get("httpx").implemented is True
    assert requesters.get("playwright").implemented is False


def test_register_replaces_same_name_without_touching_lookup() -> None:
    """同名插件可以替换，调用方仍然按名字获取。"""

    class Marker:
        name = "temp-marker"
        description = "first"
        implemented = True

    class Replacement:
        name = "temp-marker"
        description = "second"
        implemented = True

    registry: Registry[Marker] = Registry("测试")
    registry.register(Marker())
    registry.register(Replacement())  # type: ignore[arg-type]
    assert registry.get("temp-marker").description == "second"
    registry.unregister("temp-marker")
    with pytest.raises(PluginNotFoundError):
        registry.get("temp-marker")


def test_register_rejects_blank_name() -> None:
    """没有名字的对象不能进入注册表。"""

    class Blank:
        name = " "
        description = "blank"
        implemented = False

    registry: Registry[Blank] = Registry("测试")
    with pytest.raises(PluginRegistrationError):
        registry.register(Blank())

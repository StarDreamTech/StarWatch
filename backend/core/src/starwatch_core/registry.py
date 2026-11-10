"""按名称注册插件。新实现调用 register 即可，不必改调度循环。"""

from __future__ import annotations

from typing import Protocol

from starwatch_core.errors import PluginNotFoundError, PluginRegistrationError


class Described(Protocol):
    """所有槽位对象都要暴露的目录信息。"""

    name: str
    description: str
    implemented: bool


class Registry[T: Described]:
    """一个槽位的名称索引。同名注册会替换旧实现。"""

    def __init__(self, slot: str) -> None:
        """创建空注册表。

        Args:
            slot: 出现在错误信息里的槽位名称。
        """
        self.slot = slot
        self._items: dict[str, T] = {}

    def register(self, item: T) -> None:
        """注册或替换一个插件。

        Args:
            item: 带 name 属性的插件实例。

        Raises:
            PluginRegistrationError: 插件没有可用名称。
        """
        name = item.name
        if not isinstance(name, str) or not name.strip():
            raise PluginRegistrationError(f"{self.slot}缺少名称")
        self._items[name] = item

    def unregister(self, name: str) -> None:
        """移除一个插件。不存在时忽略。"""
        self._items.pop(name, None)

    def contains(self, name: str) -> bool:
        """名称是否已经注册。"""
        return name in self._items

    def get(self, name: str) -> T:
        """按名称取出插件。

        Raises:
            PluginNotFoundError: 名称未注册。
        """
        try:
            return self._items[name]
        except KeyError as exc:
            raise PluginNotFoundError(self.slot, name) from exc

    def list(self) -> list[T]:
        """按名称排序返回全部插件。"""
        return [self._items[key] for key in sorted(self._items)]

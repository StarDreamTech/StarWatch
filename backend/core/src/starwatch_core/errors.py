"""星哨领域异常。路由层把它们翻译成统一的 JSON 错误体。"""

from __future__ import annotations

from typing import Any


class StarWatchError(Exception):
    """带稳定错误码的业务异常。"""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        status_code: int = 400,
        details: dict[str, Any] | None = None,
    ) -> None:
        """记录错误码、对用户可见的说明和 HTTP 状态。

        Args:
            code: 稳定的机器可读错误码。
            message: 展示给调用方的说明。
            status_code: 对应的 HTTP 状态码。
            details: 可选的结构化补充信息。
        """
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details or {}

    def to_body(self) -> dict[str, Any]:
        """返回 API 错误响应体。"""
        return {"code": self.code, "message": self.message, "details": self.details}


class NotFoundError(StarWatchError):
    """资源不存在。"""

    def __init__(self, message: str = "资源不存在") -> None:
        """创建 404 错误。"""
        super().__init__("not_found", message, status_code=404)


class ConflictError(StarWatchError):
    """资源状态冲突，例如任务正在运行。"""

    def __init__(self, message: str) -> None:
        """创建 409 错误。"""
        super().__init__("conflict", message, status_code=409)


class ScheduleError(StarWatchError):
    """调度表达式无法解析。"""

    def __init__(self, message: str) -> None:
        """创建调度表达式错误。"""
        super().__init__("invalid_schedule", message, status_code=422)


class PluginNotFoundError(StarWatchError):
    """配置引用了未注册的插件名。"""

    def __init__(self, slot: str, name: str) -> None:
        """创建未知插件错误。

        Args:
            slot: 插件槽位的中文名称，例如「请求器」。
            name: 调用方传入的插件名。
        """
        super().__init__(
            "unknown_plugin",
            f"未知的{slot}：{name}",
            status_code=422,
            details={"slot": slot, "name": name},
        )


class PluginNotImplementedError(StarWatchError):
    """插件已注册，但还没有可用实现。"""

    def __init__(self, message: str) -> None:
        """创建未实现错误。"""
        super().__init__("not_implemented", message, status_code=501)


class PluginRegistrationError(StarWatchError):
    """插件对象缺少名称，无法注册。"""

    def __init__(self, message: str) -> None:
        """创建注册错误。"""
        super().__init__("plugin_registration", message, status_code=500)


class ProxyConfigError(StarWatchError):
    """代理参数不完整或协议不受支持。"""

    def __init__(self, message: str) -> None:
        """创建代理配置错误。"""
        super().__init__("invalid_proxy", message, status_code=422)


class ExtractError(StarWatchError):
    """提取规则无法编译或无法作用于响应体。"""

    def __init__(self, message: str) -> None:
        """创建提取错误。"""
        super().__init__("extract_error", message, status_code=422)


class FetcherUnavailableError(StarWatchError):
    """调度器无法访问抓取服务。"""

    def __init__(self, message: str = "抓取器不可用") -> None:
        """创建抓取器不可用错误。"""
        super().__init__("fetcher_unavailable", message, status_code=502)

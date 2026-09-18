"""插件注册与查找接口；不负责任何业务流程编排。"""

from typing import Any


class 插件管理器:
    def __init__(self) -> None:
        self._已注册插件: dict[str, Any] = {}

    def 注册插件(self, 插件标识: str, 插件实例: Any) -> None:
        self._已注册插件[插件标识] = 插件实例

    def 获取插件(self, 插件标识: str) -> Any:
        return self._已注册插件[插件标识]

"""全部功能插件的共同空接口。"""

from abc import ABC, abstractmethod
from typing import Any


class 基础插件接口(ABC):
    插件标识 = "未命名插件"

    @abstractmethod
    def 执行(self, 数据上下文: Any) -> Any:
        """仅由流程控制器调用；插件不得直接调用其他插件。"""
        raise NotImplementedError


class 未启用插件(基础插件接口):
    """本轮用于标记预留模块，绝不返回虚构结果。"""

    def 执行(self, 数据上下文: Any) -> dict[str, str]:
        return {"状态": "插件尚未启用", "插件": self.插件标识}

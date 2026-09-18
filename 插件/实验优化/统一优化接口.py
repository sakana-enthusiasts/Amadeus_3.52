"""实验优化策略的未来统一调用契约。"""

from abc import ABC, abstractmethod
from typing import Any


class 统一优化接口(ABC):
    @abstractmethod
    def 推荐下一轮实验(self, 实验上下文: Any) -> Any:
        raise NotImplementedError

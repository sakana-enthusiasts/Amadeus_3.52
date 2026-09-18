"""透明化预测模型的未来统一调用契约。"""

from abc import ABC, abstractmethod
from typing import Any


class 统一预测接口(ABC):
    @abstractmethod
    def 预测(self, 配方特征: Any) -> Any:
        raise NotImplementedError

"""真实数据流程的共用文件数据管理层。"""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

import pandas as pd


class 数据管理接口(ABC):
    """所有插件经由该层读写数据；页面不得直接打开论文原始表格。"""

    @abstractmethod
    def 读取论文表格(self, 文件名: str) -> pd.DataFrame:
        raise NotImplementedError

    @abstractmethod
    def 读取中间结果(self, 数据标识: str) -> pd.DataFrame:
        raise NotImplementedError

    @abstractmethod
    def 保存中间结果(self, 数据标识: str, 数据: pd.DataFrame) -> Path:
        raise NotImplementedError

    @abstractmethod
    def 保存最终结果(self, 数据标识: str, 数据: pd.DataFrame) -> Path:
        raise NotImplementedError

    @abstractmethod
    def 读取软件数据库表格(self, 文件名: str) -> pd.DataFrame:
        raise NotImplementedError

    @abstractmethod
    def 读取最终结果(self, 数据标识: str) -> pd.DataFrame:
        raise NotImplementedError

    @abstractmethod
    def 结果存在(self, 数据标识: str, 是否最终结果: bool = False) -> bool:
        raise NotImplementedError

    @abstractmethod
    def 保存筛选结果(self, 数据标识: str, 数据: pd.DataFrame) -> Path:
        raise NotImplementedError

    @abstractmethod
    def 读取筛选结果(self, 数据标识: str) -> pd.DataFrame:
        raise NotImplementedError

    @abstractmethod
    def 保存导出报告(self, 文件名: str, 内容: bytes) -> Path:
        raise NotImplementedError

    @abstractmethod
    def 保存用户导入原始文件(self, 文件名: str, 内容: bytes) -> Path:
        raise NotImplementedError


class 文件数据访问管理器(数据管理接口):
    """以 CSV 保存可审计的处理中间结果与最终统一记录。"""

    def __init__(self, 项目根目录: Path) -> None:
        self.项目根目录 = 项目根目录.resolve()
        self.论文原始数据目录 = self.项目根目录 / "数据" / "论文原始数据"
        self.中间结果目录 = self.项目根目录 / "数据" / "中间结果"
        self.模型结果目录 = self.项目根目录 / "数据" / "模型结果"
        self.筛选结果目录 = self.项目根目录 / "数据" / "筛选结果"
        self.导出结果目录 = self.项目根目录 / "数据" / "导出结果"
        self.软件数据库目录 = self.项目根目录 / "数据" / "软件数据库"
        self.用户导入数据目录 = self.项目根目录 / "数据" / "用户导入数据"

    @staticmethod
    def _标准化标识(数据标识: str) -> str:
        return 数据标识 if 数据标识.endswith(".csv") else f"{数据标识}.csv"

    def 确认目标可写入(self, 目标路径: Path) -> None:
        目标路径 = 目标路径.resolve()
        if 目标路径 == self.论文原始数据目录 or self.论文原始数据目录 in 目标路径.parents:
            raise PermissionError("论文原始数据目录默认只读，程序结果不得覆盖原始文件。")

    def 读取论文表格(self, 文件名: str) -> pd.DataFrame:
        路径 = self.论文原始数据目录 / 文件名
        if not 路径.is_file():
            raise FileNotFoundError(f"未找到论文原始表格：{路径}")
        return pd.read_excel(路径, dtype={"ID": "string", "Cat. No.": "string", "Cas No.": "string"})

    def 读取软件数据库表格(self, 文件名: str) -> pd.DataFrame:
        路径 = self.软件数据库目录 / 文件名
        if not 路径.is_file():
            raise FileNotFoundError(f"未找到软件数据库表：{路径}")
        return pd.read_csv(路径, dtype=str, keep_default_na=False)

    def 保存软件数据库表格(self, 文件名: str, 数据: pd.DataFrame) -> Path:
        return self._保存表格(self.软件数据库目录, 文件名, 数据)

    def _保存表格(self, 目录: Path, 数据标识: str, 数据: pd.DataFrame) -> Path:
        路径 = 目录 / self._标准化标识(数据标识)
        self.确认目标可写入(路径)
        目录.mkdir(parents=True, exist_ok=True)
        数据.to_csv(路径, index=False, encoding="utf-8-sig")
        return 路径

    def _读取表格(self, 目录: Path, 数据标识: str) -> pd.DataFrame:
        路径 = 目录 / self._标准化标识(数据标识)
        if not 路径.is_file():
            raise FileNotFoundError(f"未找到处理结果：{路径}")
        try:
            return pd.read_csv(路径, keep_default_na=False)
        except pd.errors.EmptyDataError:
            return pd.DataFrame()

    def 保存中间结果(self, 数据标识: str, 数据: pd.DataFrame) -> Path:
        return self._保存表格(self.中间结果目录, 数据标识, 数据)

    def 读取中间结果(self, 数据标识: str) -> pd.DataFrame:
        return self._读取表格(self.中间结果目录, 数据标识)

    def 保存最终结果(self, 数据标识: str, 数据: pd.DataFrame) -> Path:
        return self._保存表格(self.模型结果目录, 数据标识, 数据)

    def 读取最终结果(self, 数据标识: str) -> pd.DataFrame:
        路径 = self.模型结果目录 / self._标准化标识(数据标识)
        if 路径.is_file():
            return self._读取表格(self.模型结果目录, 数据标识)
        return self._读取表格(self.筛选结果目录, 数据标识)

    def 结果存在(self, 数据标识: str, 是否最终结果: bool = False) -> bool:
        if 是否最终结果:
            文件名 = self._标准化标识(数据标识)
            return ((self.模型结果目录 / 文件名).is_file() or (self.筛选结果目录 / 文件名).is_file())
        return (self.中间结果目录 / self._标准化标识(数据标识)).is_file()

    def 保存筛选结果(self, 数据标识: str, 数据: pd.DataFrame) -> Path:
        return self._保存表格(self.筛选结果目录, 数据标识, 数据)

    def 读取筛选结果(self, 数据标识: str) -> pd.DataFrame:
        return self._读取表格(self.筛选结果目录, 数据标识)

    def 保存导出报告(self, 文件名: str, 内容: bytes) -> Path:
        路径 = self.导出结果目录 / 文件名
        self.确认目标可写入(路径)
        路径.parent.mkdir(parents=True, exist_ok=True)
        路径.write_bytes(内容)
        return 路径

    def 保存用户导入原始文件(self, 文件名: str, 内容: bytes) -> Path:
        """保存上传原件的不可覆盖副本；处理结果另存至中间结果。"""
        安全文件名 = Path(文件名).name
        路径 = self.用户导入数据目录 / 安全文件名
        序号 = 1
        while 路径.exists():
            路径 = self.用户导入数据目录 / f"{Path(安全文件名).stem}_{序号}{Path(安全文件名).suffix}"
            序号 += 1
        self.确认目标可写入(路径)
        路径.parent.mkdir(parents=True, exist_ok=True)
        路径.write_bytes(内容)
        return 路径

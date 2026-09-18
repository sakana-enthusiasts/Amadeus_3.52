"""与具体论文、候选表和用途无关的 Hansen 溶解度参数计算核心。"""

from __future__ import annotations

from math import sqrt
from typing import Any, Mapping

import pandas as pd

from 插件.插件接口 import 基础插件接口


HSP字段 = ("HSP_dD", "HSP_dP", "HSP_dH")
_字段别名 = {
    "HSP_dD": ("HSP_dD", "dD", "论文_dD"),
    "HSP_dP": ("HSP_dP", "dP", "论文_dP"),
    "HSP_dH": ("HSP_dH", "dH", "论文_dH"),
}


class HSP计算核心:
    """只负责 HSP 参数标准化和 Ra 计算，不内置任何参照体系或筛选阈值。"""

    公式 = "Ra = sqrt(4*(dD1-dD2)^2 + (dP1-dP2)^2 + (dH1-dH2)^2)"

    @staticmethod
    def 参数(record: Mapping[str, Any] | pd.Series) -> dict[str, float]:
        结果: dict[str, float] = {}
        缺失: list[str] = []
        for 标准字段, 别名 in _字段别名.items():
            原值 = next((record.get(字段) for 字段 in 别名 if 字段 in record), None)
            数值 = pd.to_numeric(pd.Series([原值]), errors="coerce").iloc[0]
            if pd.isna(数值):
                缺失.append(标准字段)
            else:
                结果[标准字段] = float(数值)
        if 缺失:
            raise ValueError(f"HSP 参数缺失：{'、'.join(缺失)}")
        return 结果

    @classmethod
    def 计算距离(cls, 物质1: Mapping[str, Any] | pd.Series, 物质2: Mapping[str, Any] | pd.Series) -> float:
        参数1, 参数2 = cls.参数(物质1), cls.参数(物质2)
        return sqrt(
            4 * (参数1["HSP_dD"] - 参数2["HSP_dD"]) ** 2
            + (参数1["HSP_dP"] - 参数2["HSP_dP"]) ** 2
            + (参数1["HSP_dH"] - 参数2["HSP_dH"]) ** 2
        )

    @classmethod
    def 评估(cls, 候选: Mapping[str, Any] | pd.Series, 参照: Mapping[str, Any] | pd.Series) -> dict[str, Any]:
        """将缺失显式返回，供用途插件决定后续如何处理。"""
        try:
            候选参数, 参照参数 = cls.参数(候选), cls.参数(参照)
        except ValueError as 错误:
            return {"HSP状态": "无法评估", "HSP原因": str(错误), "汉森距离_Ra": pd.NA}
        return {
            **{f"候选_{字段}": 值 for 字段, 值 in 候选参数.items()},
            **{f"参照_{字段}": 值 for 字段, 值 in 参照参数.items()},
            "汉森距离_Ra": round(cls.计算距离(候选参数, 参照参数), 6),
            "HSP状态": "已计算",
            "HSP原因": "",
            "计算公式": cls.公式,
        }


class 通用HSP计算插件(基础插件接口):
    """以显式传入的候选和参照计算全部两两距离。"""

    插件标识 = "通用HSP计算"

    def 执行(self, 数据上下文: dict[str, Any]) -> pd.DataFrame:
        原候选, 原参照 = 数据上下文.get("HSP候选"), 数据上下文.get("HSP参照")
        候选 = 原候选.copy() if isinstance(原候选, pd.DataFrame) else pd.DataFrame([] if 原候选 is None else 原候选)
        参照 = 原参照.copy() if isinstance(原参照, pd.DataFrame) else pd.DataFrame([] if 原参照 is None else 原参照)
        if 候选.empty or 参照.empty:
            return pd.DataFrame(columns=["候选标识", "参照标识", "汉森距离_Ra", "HSP状态", "HSP原因"])
        记录: list[dict[str, Any]] = []
        for _, 候选行 in 候选.iterrows():
            for _, 参照行 in 参照.iterrows():
                记录.append({
                    "候选标识": str(候选行.get("成分键", 候选行.get("候选编号", 候选行.get("名称", "")))),
                    "参照标识": str(参照行.get("参照体系", 参照行.get("成分键", 参照行.get("名称", 参照行.get("候选编号", ""))))),
                    **HSP计算核心.评估(候选行, 参照行),
                })
        return pd.DataFrame(记录)

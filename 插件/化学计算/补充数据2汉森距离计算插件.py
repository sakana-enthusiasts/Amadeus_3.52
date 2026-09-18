"""计算补充数据2候选与 BA、VA 的 Hansen 距离，并显式处理缺失。"""

from __future__ import annotations

from typing import Any

import pandas as pd

from 插件.插件接口 import 基础插件接口
from 插件.化学计算.HSP计算核心 import HSP计算核心


class 补充数据2汉森距离计算插件(基础插件接口):
    插件标识 = "补充数据2汉森距离计算"
    输入标识 = "补充数据2_数值初筛记录"
    输出标识 = "补充数据2_汉森距离结果"
    公式 = "Ra = sqrt(4*(dD1-dD2)^2 + (dP1-dP2)^2 + (dH1-dH2)^2)"
    参照CAS = {"BA": "100-51-6", "VA": "93-03-8"}
    参数列 = ("论文_dD", "论文_dP", "论文_dH")

    @classmethod
    def _唯一参照(cls, 全部候选: pd.DataFrame, 名称: str, CAS号: str) -> pd.Series:
        命中 = 全部候选.loc[全部候选["论文_CAS号"].astype(str).str.strip().eq(CAS号)]
        if len(命中) != 1:
            raise ValueError(f"Hansen 参照 {名称}（CAS {CAS号}）必须唯一，当前找到 {len(命中)} 条记录")
        参照 = 命中.iloc[0].copy()
        缺失 = [列 for 列 in cls.参数列 if pd.isna(参照[列])]
        if 缺失:
            raise ValueError(f"Hansen 参照 {名称}（CAS {CAS号}）缺少参数：{'、'.join(缺失)}")
        return 参照

    @classmethod
    def _距离(cls, 候选: pd.Series, 参照: pd.Series) -> float:
        return HSP计算核心.计算距离(候选, 参照)

    def 执行(self, 数据上下文: dict[str, Any]) -> pd.DataFrame:
        数据管理器 = 数据上下文["数据管理器"]
        全部候选 = 数据管理器.读取中间结果(self.输入标识).copy()
        缺列 = {"候选编号", "论文_CAS号", "数值初筛通过", *self.参数列} - set(全部候选.columns)
        if 缺列:
            raise ValueError(f"Hansen 距离输入缺少字段：{sorted(缺列)}")
        for 字段 in self.参数列:
            全部候选[字段] = pd.to_numeric(全部候选[字段], errors="coerce")
        参照 = {名称: self._唯一参照(全部候选, 名称, CAS号) for 名称, CAS号 in self.参照CAS.items()}
        初筛通过 = 全部候选["数值初筛通过"].astype(str).str.lower().eq("true")
        记录: list[dict[str, Any]] = []
        for _, 候选 in 全部候选.loc[初筛通过].iterrows():
            缺失 = [字段 for 字段 in self.参数列 if pd.isna(候选[字段])]
            for 参照编号, 参照试剂 in 参照.items():
                基础 = {
                    "候选编号": 候选["候选编号"],
                    "候选名称": 候选.get("论文_化学名称", ""),
                    "参照试剂编号": 参照编号,
                    "参照试剂名称": 参照试剂.get("论文_化学名称", ""),
                    "候选_dD": 候选["论文_dD"],
                    "候选_dP": 候选["论文_dP"],
                    "候选_dH": 候选["论文_dH"],
                    "参照_dD": 参照试剂["论文_dD"],
                    "参照_dP": 参照试剂["论文_dP"],
                    "参照_dH": 参照试剂["论文_dH"],
                    "计算公式": self.公式,
                    "数据来源": "SeeThrough Supplementary Data 2",
                }
                if 缺失:
                    记录.append(基础 | {"汉森距离_Ra": pd.NA, "规则状态": "无法评估", "无法评估原因": f"HSP 参数缺失：{'、'.join(缺失)}"})
                else:
                    记录.append(基础 | {"汉森距离_Ra": round(self._距离(候选, 参照试剂), 6), "规则状态": "通过", "无法评估原因": ""})
        结果 = pd.DataFrame(记录)
        数据管理器.保存中间结果(self.输出标识, 结果)
        return 结果

"""将论文标签降级为可选验证数据，绝不作为正式筛选输入。"""

from __future__ import annotations

from typing import Any

import pandas as pd

from 插件.插件接口 import 基础插件接口


class 补充数据2属性合并插件(基础插件接口):
    插件标识 = "补充数据2属性合并"
    输入标识 = "补充数据2_规则筛选统一记录"
    输出标识 = "补充数据2_规则筛选统一记录"
    标签文件 = "补充数据2论文最终10标签表.csv"

    @staticmethod
    def _候选列(表格: pd.DataFrame) -> str:
        for 列 in ("候选编号", "论文候选编号", "ID", "Candidate ID"):
            if 列 in 表格.columns:
                return 列
        raise ValueError("标签表或筛选结果缺少候选编号列")

    @staticmethod
    def _标签列(标签: pd.DataFrame) -> str | None:
        for 列 in ("论文最终10候选标签", "最终10候选标签", "标签"):
            if 列 in 标签.columns:
                return 列
        return None

    def _追加标签验证(self, 数据管理器: Any, 记录: pd.DataFrame, 标签: pd.DataFrame) -> None:
        记录键 = self._候选列(记录)
        标签键 = self._候选列(标签)
        标签列 = self._标签列(标签)
        if not 标签列:
            return
        自动列 = "自动规则通过"
        if 自动列 not in 记录.columns:
            raise ValueError("正式筛选记录缺少自动规则通过列")
        选择集 = set(记录.loc[记录[自动列].astype(str).str.lower().eq("true"), 记录键].astype(str))
        标注集 = set(标签.loc[标签[标签列].astype(str).isin(["是", "true", "True", "1"]), 标签键].astype(str))
        命中 = 选择集 & 标注集
        召回率 = len(命中) / len(标注集) if 标注集 else None
        验证 = pd.DataFrame([{
            "标签验证状态": "已执行",
            "标签文件": self.标签文件,
            "自动候选数": len(选择集),
            "标签候选数": len(标注集),
            "候选重叠数": len(命中),
            "召回率": 召回率,
            "仅自动候选": "|".join(sorted(选择集 - 标注集)),
            "仅标签候选": "|".join(sorted(标注集 - 选择集)),
        }])
        数据管理器.保存筛选结果("补充数据2_论文标签验证统计", 验证)

    def 执行(self, 数据上下文: dict[str, Any]) -> pd.DataFrame:
        数据管理器 = 数据上下文["数据管理器"]
        记录 = 数据管理器.读取筛选结果(self.输入标识).copy()
        try:
            标签 = 数据管理器.读取软件数据库表格(self.标签文件).copy()
        except FileNotFoundError:
            标签 = pd.DataFrame()
        if 标签.empty:
            记录["论文最终10候选标签"] = "未提供验证标签"
            记录["论文标签验证状态"] = "未执行：标签文件不存在或为空"
        else:
            记录键 = self._候选列(记录)
            标签键 = self._候选列(标签)
            标签列 = self._标签列(标签)
            if 标签列:
                标签子集 = 标签[[标签键, 标签列]].drop_duplicates(标签键).rename(columns={标签键: 记录键})
                记录 = 记录.merge(标签子集, how="left", on=记录键, suffixes=("", "_标签"))
                if f"{标签列}_标签" in 记录.columns:
                    记录["论文最终10候选标签"] = 记录[f"{标签列}_标签"].fillna("未标注")
                    记录 = 记录.drop(columns=[f"{标签列}_标签"])
                elif 标签列 != "论文最终10候选标签":
                    记录["论文最终10候选标签"] = 记录[标签列].fillna("未标注")
                else:
                    记录["论文最终10候选标签"] = 记录[标签列].fillna("未标注")
                记录["论文标签验证状态"] = "已追加验证标签；未参与筛选"
                self._追加标签验证(数据管理器, 记录, 标签)
            else:
                记录["论文最终10候选标签"] = "标签表无可识别标签列"
                记录["论文标签验证状态"] = "未执行：标签列不可识别"
        数据管理器.保存筛选结果(self.输出标识, 记录)
        数据管理器.保存最终结果(self.输出标识, 记录)
        return 记录

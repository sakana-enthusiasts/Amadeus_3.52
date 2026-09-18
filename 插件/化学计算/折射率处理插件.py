"""折射率数据的通用整理与目标差值计算；不臆造浓度或混合液模型。"""

from typing import Any

import pandas as pd

from 插件.插件接口 import 基础插件接口


class 折射率处理插件(基础插件接口):
    插件标识 = "折射率处理"

    def 执行(self, 数据上下文: dict[str, Any]) -> pd.DataFrame:
        原始 = 数据上下文.get("成分")
        成分 = 原始.copy() if isinstance(原始, pd.DataFrame) else pd.DataFrame([] if 原始 is None else 原始)
        if 成分.empty:
            return pd.DataFrame(columns=["成分键", "纯物质RI", "浓度下RI", "RI数据状态", "RI与目标差值"])
        目标RI = pd.to_numeric(pd.Series([数据上下文.get("目标折射率", 1.56)]), errors="coerce").iloc[0]
        if pd.isna(目标RI):
            raise ValueError("折射率处理需要有效的目标折射率")
        for 字段 in ("纯物质RI", "浓度下RI"):
            if 字段 not in 成分:
                成分[字段] = pd.NA
            成分[字段] = pd.to_numeric(成分[字段], errors="coerce")
        成分["RI数据状态"] = 成分.apply(lambda 行: "已有浓度下RI" if pd.notna(行["浓度下RI"]) else ("已有纯物质RI，待测RI(浓度)" if pd.notna(行["纯物质RI"]) else "待补RI数据"), axis=1)
        成分["RI与目标差值"] = 成分["浓度下RI"].map(lambda 值: round(float(值) - float(目标RI), 6) if pd.notna(值) else pd.NA)
        return 成分[[字段 for 字段 in ("成分键", "候选编号", "纯物质RI", "浓度下RI", "RI数据状态", "RI与目标差值") if 字段 in 成分]].copy()

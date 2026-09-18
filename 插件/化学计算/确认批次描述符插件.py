"""将已确认化合物清单转为不可覆盖的批次级通用化学描述符。"""

from __future__ import annotations

from typing import Any

import pandas as pd
from rdkit import Chem

from 插件.化学计算.RDKit普通描述符插件 import RDKit普通描述符插件
from 插件.插件接口 import 基础插件接口


class 确认批次描述符插件(基础插件接口):
    插件标识 = "确认批次化学描述符"

    @staticmethod
    def _成分键(行: pd.Series) -> str:
        return str(行.get("成分键") or f"{行.get('来源运行编号', '')}::{行.get('候选编号', '')}")

    def 执行(self, 数据上下文: dict[str, Any]) -> pd.DataFrame:
        原始 = 数据上下文.get("确认清单")
        清单 = 原始.copy() if isinstance(原始, pd.DataFrame) else pd.DataFrame([] if 原始 is None else 原始)
        批次编号 = str(数据上下文.get("批次编号", ""))
        记录: list[dict[str, Any]] = []
        描述符插件 = RDKit普通描述符插件()
        for _, 行 in 清单.iterrows():
            SMILES = next((str(行.get(字段, "") or "").strip() for 字段 in ("Isomeric SMILES", "Canonical SMILES", "结构映射_SMILES") if str(行.get(字段, "") or "").strip()), "")
            分子 = Chem.MolFromSmiles(SMILES) if SMILES else None
            基础 = {"批次编号": 批次编号, "成分键": self._成分键(行), "候选编号": str(行.get("候选编号", "")), "化学名称": str(行.get("化学名称", "")), "SMILES": SMILES, "计算工具": "RDKit", "工具版本": 描述符插件.工具版本}
            if 分子 is None:
                记录.append({**基础, "描述符名称": "结构状态", "数值": "", "是否计算成功": False, "失败原因": "确认清单缺少有效 SMILES"})
                continue
            for 名称, 数值 in (描述符插件._描述符值(分子) | 描述符插件._Fig1c标签(分子)).items():
                记录.append({**基础, "描述符名称": 名称, "数值": 数值, "是否计算成功": True, "失败原因": ""})
        return pd.DataFrame(记录)

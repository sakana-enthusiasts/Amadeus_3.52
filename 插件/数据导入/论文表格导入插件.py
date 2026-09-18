"""导入 SeeThrough 补充数据3，形成统一候选基础记录。"""

from typing import Any

import pandas as pd

from 插件.插件接口 import 基础插件接口


class 论文表格导入插件(基础插件接口):
    插件标识 = "论文表格导入"
    补充数据3文件名 = "SeeThrough补充数据3_最终候选与混合折射率.xlsx"
    输出标识 = "补充数据3_统一候选基础记录"

    def 执行(self, 数据上下文: dict[str, Any]) -> pd.DataFrame:
        数据管理器 = 数据上下文["数据管理器"]
        原始表 = 数据管理器.读取论文表格(self.补充数据3文件名)
        必需列 = {"ID", "Chemical Name", "Cat. No.", "Cas No.", "eRI (RI*)", "dD", "dP", "dH", "RI with BA", "RI with VA"}
        缺失列 = 必需列 - set(原始表.columns)
        if 缺失列:
            raise ValueError(f"补充数据3缺少必要列：{sorted(缺失列)}")

        结果 = pd.DataFrame(
            {
                "候选编号": 原始表["ID"].fillna("").astype(str),
                "论文ID": 原始表["ID"].fillna("").astype(str),
                "论文_化学名称": 原始表["Chemical Name"].fillna("").astype(str),
                "论文_货号": 原始表["Cat. No."].fillna("").astype(str),
                "论文_CAS号": 原始表["Cas No."].fillna("").astype(str),
                "论文_eRI原始": 原始表["eRI (RI*)"].fillna("").astype(str),
                "论文_eRI数值": pd.to_numeric(原始表["eRI (RI*)"].astype(str).str.replace("*", "", regex=False), errors="coerce"),
                "论文_dD": pd.to_numeric(原始表["dD"], errors="coerce"),
                "论文_dP": pd.to_numeric(原始表["dP"], errors="coerce"),
                "论文_dH": pd.to_numeric(原始表["dH"], errors="coerce"),
                "论文_与BA混合折射率": pd.to_numeric(原始表["RI with BA"], errors="coerce"),
                "论文_与VA混合折射率": pd.to_numeric(原始表["RI with VA"], errors="coerce"),
                "论文数据来源": "SeeThrough Supplementary Data 3",
            }
        )
        参照编号 = {"100-51-6": "BA", "93-03-8": "VA"}
        空编号 = 结果["候选编号"].eq("")
        结果.loc[空编号, "候选编号"] = 结果.loc[空编号, "论文_CAS号"].map(参照编号).fillna("")
        结果["试剂角色"] = 结果["候选编号"].map({"BA": "有机相参照", "VA": "有机相参照"}).fillna("水相候选")
        结果["论文ID缺失"] = 结果["论文ID"].eq("")
        数据管理器.保存中间结果(self.输出标识, 结果)
        return 结果

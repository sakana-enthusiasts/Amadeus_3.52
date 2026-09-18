"""保存官方补充数据2/3同一试剂的可追溯属性冲突，不静默覆盖。"""

from typing import Any
import math

import pandas as pd

from 插件.插件接口 import 基础插件接口


class 官方数据冲突检测插件(基础插件接口):
    插件标识 = "官方数据冲突检测"
    输出标识 = "补充数据2与3_官方数据冲突记录"

    @staticmethod
    def _Ra(甲: pd.Series, 乙: pd.Series) -> float:
        return math.sqrt(4 * (float(甲["论文_dD"]) - float(乙["论文_dD"])) ** 2 + (float(甲["论文_dP"]) - float(乙["论文_dP"])) ** 2 + (float(甲["论文_dH"]) - float(乙["论文_dH"])) ** 2)

    def 执行(self, 数据上下文: dict[str, Any]) -> pd.DataFrame:
        数据管理器 = 数据上下文["数据管理器"]
        数据2 = 数据管理器.读取中间结果("补充数据2_统一候选记录").copy()
        数据3 = 数据管理器.读取中间结果("补充数据3_统一候选基础记录").copy()
        数据2["匹配键"] = 数据2["论文_CAS号"].astype(str).where(数据2["论文_CAS号"].astype(str).ne(""), 数据2["候选编号"].astype(str))
        数据3["匹配键"] = 数据3["论文_CAS号"].astype(str).where(数据3["论文_CAS号"].astype(str).ne(""), 数据3["候选编号"].astype(str))
        合并 = 数据2.merge(数据3, on="匹配键", how="inner", suffixes=("_数据2", "_数据3"))
        BA = 数据2.loc[数据2["论文_CAS号"].eq("100-51-6")].iloc[0]
        记录 = []
        字段映射 = [("化学名称", "论文_化学名称_数据2", "论文_化学名称_数据3"), ("CAS", "论文_CAS号_数据2", "论文_CAS号_数据3"), ("eRI", "论文_eRI", "论文_eRI数值"), ("dD", "论文_dD_数据2", "论文_dD_数据3"), ("dP", "论文_dP_数据2", "论文_dP_数据3"), ("dH", "论文_dH_数据2", "论文_dH_数据3")]
        for _, 行 in 合并.iterrows():
            for 字段, 列2, 列3 in 字段映射:
                值2, 值3 = str(行.get(列2, "")), str(行.get(列3, ""))
                try:
                    不同 = not math.isclose(float(值2), float(值3), rel_tol=1e-9, abs_tol=1e-9)
                except ValueError:
                    不同 = 值2.strip() != 值3.strip()
                if 不同:
                    敏感性 = "不适用"
                    if 字段 in {"dD", "dP", "dH"}:
                        参数2 = {"论文_dD": 行["论文_dD_数据2"], "论文_dP": 行["论文_dP_数据2"], "论文_dH": 行["论文_dH_数据2"]}
                        参数3 = {"论文_dD": 行["论文_dD_数据3"], "论文_dP": 行["论文_dP_数据3"], "论文_dH": 行["论文_dH_数据3"]}
                        ra2, ra3 = self._Ra(pd.Series(参数2), BA), self._Ra(pd.Series(参数3), BA)
                        敏感性 = f"Ra(BA)：数据2={ra2:.6f}，数据3={ra3:.6f}；结论{'不变' if (ra2 < 10) == (ra3 < 10) else '改变'}"
                    记录.append({"候选编号": 行["候选编号_数据2"], "化学名称": 行["论文_化学名称_数据2"], "字段名称": 字段, "补充数据2的值": 值2, "补充数据3的值": 值3, "补充数据2来源": "SeeThrough Supplementary Data 2", "补充数据3来源": "SeeThrough Supplementary Data 3", "当前筛选采用的值": 值2, "采用理由": "1619候选库及自动筛选参数来自补充数据2", "是否影响通过或排除结果": 敏感性})
        结果 = pd.DataFrame(记录)
        数据管理器.保存筛选结果(self.输出标识, 结果)
        return 结果

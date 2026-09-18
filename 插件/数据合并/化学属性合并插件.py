"""合并论文原始字段、结构、RDKit 描述符与 Hansen 距离，保留字段来源。"""

from typing import Any

import pandas as pd

from 插件.插件接口 import 基础插件接口


class 化学属性合并插件(基础插件接口):
    插件标识 = "化学属性合并"
    结构输入标识 = "补充数据3_结构映射结果"
    描述符输入标识 = "补充数据3_RDKit描述符结果"
    汉森输入标识 = "补充数据3_汉森距离结果"
    输出标识 = "补充数据3_化学属性统一记录"

    def 执行(self, 数据上下文: dict[str, Any]) -> pd.DataFrame:
        数据管理器 = 数据上下文["数据管理器"]
        候选表 = 数据管理器.读取中间结果(self.结构输入标识)
        描述符表 = 数据管理器.读取中间结果(self.描述符输入标识)
        汉森表 = 数据管理器.读取中间结果(self.汉森输入标识)

        描述符透视表 = 描述符表.pivot(index="候选编号", columns="描述符名称", values="数值").reset_index()
        描述符透视表 = 描述符透视表.rename(columns={列: f"RDKit_{列}" for 列 in 描述符透视表.columns if 列 != "候选编号"})
        汉森透视表 = 汉森表.pivot(index="候选编号", columns="参照试剂编号", values="汉森距离_Ra").reset_index()
        汉森透视表 = 汉森透视表.rename(columns={"BA": "汉森距离_与BA", "VA": "汉森距离_与VA"})

        统一记录 = 候选表.merge(描述符透视表, on="候选编号", how="left", validate="one_to_one")
        统一记录 = 统一记录.merge(汉森透视表, on="候选编号", how="left", validate="one_to_one")
        统一记录["论文原始字段来源"] = "SeeThrough Supplementary Data 3"
        统一记录["分子结构来源"] = 统一记录["结构映射_来源"].fillna("")
        统一记录["RDKit描述符来源"] = "RDKit 实际计算"
        统一记录["汉森距离来源"] = "SeeThrough Supplementary Data 3 参数；独立 Hansen 距离插件计算"

        必需字段 = ["结构映射_SMILES", "论文_dD", "论文_dP", "论文_dH"]
        缺失项 = pd.Series("", index=统一记录.index, dtype=str)
        for 字段 in 必需字段:
            缺失项 = 缺失项.mask(统一记录[字段].isna() | 统一记录[字段].astype(str).eq(""), 缺失项 + f"{字段};")
        成功掩码 = 描述符表["是否计算成功"].astype(str).str.lower().eq("true")
        描述符失败 = 描述符表.loc[~成功掩码, ["候选编号", "失败原因"]]
        描述符错误 = 描述符失败.groupby("候选编号")["失败原因"].agg(lambda 值: ";".join(sorted(set(值.astype(str))))).rename("RDKit错误信息")
        统一记录 = 统一记录.merge(描述符错误, on="候选编号", how="left")
        统一记录["缺失状态"] = 缺失项.str.rstrip(";").where(缺失项.ne(""), "无关键字段缺失")
        统一记录["错误信息"] = 统一记录["结构错误信息"].fillna("") + 统一记录["RDKit错误信息"].fillna("")
        数据管理器.保存最终结果(self.输出标识, 统一记录)
        return 统一记录

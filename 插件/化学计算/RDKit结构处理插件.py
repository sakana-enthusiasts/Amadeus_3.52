"""根据经人工核对的结构映射表验证补充数据3的 RDKit 结构。"""

from datetime import datetime, timezone
from typing import Any

import pandas as pd
import requests
from rdkit import Chem

from 插件.插件接口 import 基础插件接口


class RDKit结构处理插件(基础插件接口):
    插件标识 = "RDKit结构处理"
    输入标识 = "补充数据3_统一候选基础记录"
    输出标识 = "补充数据3_结构映射结果"
    映射表文件名 = "补充数据3结构映射表.csv"

    @staticmethod
    def _验证结构(行: pd.Series) -> pd.Series:
        smiles = str(行.get("结构映射_SMILES", "") or "").strip()
        if not smiles:
            return pd.Series({"结构状态": "缺失", "结构错误信息": str(行.get("结构查询失败原因", "结构映射表中无 SMILES"))})
        if Chem.MolFromSmiles(smiles) is None:
            return pd.Series({"结构状态": "无效", "结构错误信息": "RDKit 无法读取映射 SMILES"})
        return pd.Series({"结构状态": "已获得", "结构错误信息": ""})

    def _查询PubChem(self, 候选编号: str, CAS号: str, 化学名称: str) -> dict[str, str]:
        基础 = {"候选编号": 候选编号, "CAS号": CAS号, "论文化学名称": 化学名称,
                "结构来源": "PubChem PUG REST（CAS 查询）", "查询时间": datetime.now(timezone.utc).isoformat(),
                "PubChem CID": "", "PubChem返回名称": "", "SMILES": "", "名称核对状态": "", "结构查询失败原因": ""}
        try:
            属性网址 = f"https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/name/{CAS号}/property/CanonicalSMILES,IUPACName/JSON"
            响应 = requests.get(属性网址, timeout=20)
            响应.raise_for_status()
            属性 = 响应.json()["PropertyTable"]["Properties"][0]
            CID = str(属性.get("CID", ""))
            基础.update({"PubChem CID": CID, "PubChem返回名称": str(属性.get("IUPACName", "")), "SMILES": str(属性.get("ConnectivitySMILES", 属性.get("CanonicalSMILES", "")))})
            标准名 = "".join(ch for ch in 化学名称.lower() if ch.isalnum())
            返回名 = "".join(ch for ch in str(属性.get("IUPACName", "")).lower() if ch.isalnum())
            基础["名称核对状态"] = "名称近似一致" if 标准名 and (标准名 in 返回名 or 返回名 in 标准名) else "CAS查询成功；名称可能为同义名，需人工复核"
        except Exception as 错误:  # 网络失败保留为可审计缓存，避免盲目重试
            基础["名称核对状态"] = "未核对"
            基础["结构查询失败原因"] = f"PubChem 查询失败：{错误}"
        return 基础

    def _执行补充数据2结构处理(self, 数据管理器: Any) -> pd.DataFrame:
        候选表 = 数据管理器.读取中间结果("补充数据2_数值初筛记录").copy()
        候选表 = 候选表[候选表["数值初筛通过"].astype(str).str.lower().eq("true")].copy()
        缓存文件 = "补充数据2结构缓存.csv"
        try:
            缓存 = 数据管理器.读取软件数据库表格(缓存文件)
        except FileNotFoundError:
            缓存 = pd.DataFrame()
        已缓存 = {str(行["CAS号"]): 行.to_dict() for _, 行 in 缓存.iterrows()} if not 缓存.empty else {}
        新记录 = []
        for _, 行 in 候选表.iterrows():
            CAS号 = str(行["论文_CAS号"])
            缓存记录 = 已缓存.get(CAS号)
            if 缓存记录 is None:
                缓存记录 = self._查询PubChem(str(行["候选编号"]), CAS号, str(行["论文_化学名称"]))
                已缓存[CAS号] = 缓存记录
            新记录.append(缓存记录)
        缓存结果 = pd.DataFrame(list(已缓存.values()))
        数据管理器.保存软件数据库表格(缓存文件, 缓存结果)
        映射 = pd.DataFrame(新记录).rename(columns={"CAS号": "论文_CAS号", "SMILES": "结构映射_SMILES", "PubChem CID": "结构映射_PubChemCID", "PubChem返回名称": "结构映射_PubChem名称", "结构来源": "结构映射_来源", "名称核对状态": "结构映射_名称核对状态"})
        结果 = 候选表.merge(映射.drop(columns=["候选编号", "论文化学名称"], errors="ignore"), on="论文_CAS号", how="left", validate="one_to_one")
        if "结构映射_SMILES" not in 结果:
            结果["结构映射_SMILES"] = ""
        结果[["结构状态", "结构错误信息"]] = 结果.apply(self._验证结构, axis=1)
        try:
            身份 = 数据管理器.读取中间结果("补充数据2_41候选身份映射")
            身份 = 身份.rename(columns={"Isomeric SMILES": "身份_Isomeric_SMILES", "PubChem CID": "身份_PubChemCID", "查询来源": "身份_查询来源", "匹配状态": "身份_匹配状态"})
            结果 = 结果.merge(身份[[列 for 列 in ["候选编号", "身份_Isomeric_SMILES", "身份_PubChemCID", "身份_查询来源", "身份_匹配状态", "InChIKey", "是否为盐", "是否为水合物或溶剂化物", "是否为混合物", "未定义立体结构", "冲突说明"] if 列 in 身份.columns]], on="候选编号", how="left", validate="one_to_one")
            有身份结构 = 结果["身份_Isomeric_SMILES"].fillna("").astype(str).str.strip().ne("")
            结果.loc[有身份结构, "结构映射_SMILES"] = 结果.loc[有身份结构, "身份_Isomeric_SMILES"]
            结果.loc[有身份结构, "结构映射_PubChemCID"] = 结果.loc[有身份结构, "身份_PubChemCID"]
            结果.loc[有身份结构, "结构映射_来源"] = 结果.loc[有身份结构, "身份_查询来源"]
            结果[["结构状态", "结构错误信息"]] = 结果.apply(self._验证结构, axis=1)
        except FileNotFoundError:
            pass
        数据管理器.保存中间结果("补充数据2_结构映射结果", 结果)
        return 结果

    def 执行(self, 数据上下文: dict[str, Any]) -> pd.DataFrame:
        数据管理器 = 数据上下文["数据管理器"]
        if 数据上下文.get("补充数据2结构处理"):
            return self._执行补充数据2结构处理(数据管理器)
        if 数据上下文.get("用户结构处理"):
            候选 = 数据管理器.读取中间结果("用户导入_统一候选记录")
            身份 = 数据管理器.读取中间结果("用户导入_化合物身份映射")
            字段 = [列 for 列 in ["候选编号", "Isomeric SMILES", "PubChem CID", "查询来源", "匹配状态"] if 列 in 身份]
            结果 = 候选.merge(身份[字段], on="候选编号", how="left", validate="one_to_one")
            结果 = 结果.rename(columns={"Isomeric SMILES": "结构映射_SMILES", "PubChem CID": "结构映射_PubChemCID", "查询来源": "结构映射_来源", "匹配状态": "身份_匹配状态"})
            结果[["结构状态", "结构错误信息"]] = 结果.apply(self._验证结构, axis=1)
            数据管理器.保存中间结果("用户导入_结构映射结果", 结果)
            return 结果
        候选表 = 数据管理器.读取中间结果(self.输入标识)
        映射表 = 数据管理器.读取软件数据库表格(self.映射表文件名)
        映射表 = 映射表.rename(
            columns={
                "论文候选编号": "结构映射_候选编号",
                "论文名称": "结构映射_论文名称",
                "CAS号": "结构映射_CAS号",
                "SMILES": "结构映射_SMILES",
                "PubChemCID": "结构映射_PubChemCID",
                "PubChem名称": "结构映射_PubChem名称",
                "结构来源URL": "结构映射_来源URL",
                "结构来源": "结构映射_来源",
                "人工核对状态": "结构映射_人工核对状态",
                "结构状态": "结构映射_声明状态",
                "错误原因": "结构映射_声明错误",
            }
        )
        结果 = 候选表.merge(
            映射表,
            how="left",
            left_on="论文_CAS号",
            right_on="结构映射_CAS号",
            validate="one_to_one",
        )

        结果[["结构状态", "结构错误信息"]] = 结果.apply(self._验证结构, axis=1)
        数据管理器.保存中间结果(self.输出标识, 结果)
        return 结果

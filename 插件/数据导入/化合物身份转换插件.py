"""CAS优先的PubChem身份转换；不确定的多CID不自动选择结构。"""

from datetime import datetime, timezone
import re
from typing import Any
from urllib.parse import quote

import pandas as pd
import requests

from 插件.插件接口 import 基础插件接口


class 化合物身份转换插件(基础插件接口):
    插件标识 = "化合物身份转换"
    缓存文件 = "化合物身份缓存.csv"
    冲突标识 = "化合物身份冲突表"

    @staticmethod
    def _缓存主键(行: pd.Series | dict[str, Any]) -> str:
        取值 = lambda 键: str(行.get(键, "") or "").strip()
        CAS = 取值("原始CAS")
        if re.fullmatch(r"\d{2,7}-\d{2}-\d", CAS):
            return f"CAS:{CAS}"
        InChIKey = 取值("InChIKey")
        if InChIKey:
            return f"InChIKey:{InChIKey}"
        名称 = re.sub(r"[^a-z0-9]", "", 取值("原始名称").lower())
        return f"名称文件编号:{名称}|{取值('原始文件')}|{取值('候选编号')}"

    @staticmethod
    def _形式标记(名称: str, SMILES: str) -> dict[str, str]:
        文本 = 名称.lower()
        盐 = bool(re.search(r"hydrochloride|sodium|potassium|calcium|sulfate|phosphate|\.cl|\[na\+\]", 文本 + SMILES.lower()))
        水合 = bool(re.search(r"hydrate|monohydrate|dihydrate|solvate", 文本))
        混合 = bool(re.search(r"mixture|contains varying amounts|stabilized with", 文本))
        return {"是否为盐": "是" if 盐 else "否", "是否为水合物或溶剂化物": "是" if 水合 else "否", "是否为混合物": "是" if 混合 else "否", "未定义立体结构": "未见显式立体标记（不等于存在手性未定义）" if "@" not in SMILES else "含显式立体标记"}

    @staticmethod
    def _获取CID(查询值: str) -> list[int]:
        地址 = f"https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/name/{quote(查询值, safe='')}/cids/JSON"
        响应 = requests.get(地址, timeout=20)
        if 响应.status_code == 404:
            return []
        响应.raise_for_status()
        return [int(x) for x in 响应.json().get("IdentifierList", {}).get("CID", [])]

    @staticmethod
    def _获取属性(CID: int) -> dict[str, str]:
        属性 = "IUPACName,IsomericSMILES,CanonicalSMILES,InChI,InChIKey,MolecularFormula"
        地址 = f"https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/cid/{CID}/property/{属性}/JSON"
        响应 = requests.get(地址, timeout=20)
        响应.raise_for_status()
        return 响应.json()["PropertyTable"]["Properties"][0]

    @staticmethod
    def _批量获取属性(CID列表: list[int]) -> dict[str, dict[str, str]]:
        if not CID列表:
            return {}
        属性 = "IUPACName,IsomericSMILES,CanonicalSMILES,InChI,InChIKey,MolecularFormula"
        地址 = f"https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/cid/{','.join(map(str, CID列表))}/property/{属性}/JSON"
        响应 = requests.get(地址, timeout=30)
        响应.raise_for_status()
        return {str(值["CID"]): 值 for 值 in 响应.json()["PropertyTable"]["Properties"]}

    def _转换一条(self, 行: pd.Series) -> tuple[dict[str, str], list[dict[str, str]]]:
        名称, CAS = str(行.get("原始名称", 行.get("论文_化学名称", ""))).strip(), str(行.get("原始CAS", 行.get("论文_CAS号", ""))).strip()
        基础 = {"候选编号": str(行["候选编号"]), "原始名称": 名称, "原始CAS": CAS, "原始货号": str(行.get("原始货号", 行.get("论文_货号", ""))), "查询方式": "", "PubChem CID": "", "PubChem标准名称": "", "Isomeric SMILES": "", "Canonical SMILES": "", "InChI": "", "InChIKey": "", "分子式": "", "查询来源": "PubChem PUG REST", "查询时间": datetime.now(timezone.utc).isoformat(), "匹配状态": "未查询", "冲突说明": "", "自动匹配或人工确认": "自动匹配"}
        冲突: list[dict[str, str]] = []
        try:
            CAS_CID = self._获取CID(CAS) if CAS else []
            名称_CID = self._获取CID(名称) if 名称 else []
            选择CID, 查询方式 = (CAS_CID, "CAS") if CAS_CID else (名称_CID, "化学名称")
            基础["查询方式"] = 查询方式 or "无结果"
            if CAS_CID and 名称_CID and set(CAS_CID) != set(名称_CID):
                冲突.append({**基础, "冲突类型": "CAS查询和名称查询得到不同CID", "来源值一": str(CAS_CID), "来源值二": str(名称_CID), "当前采用值": "未自动采用", "采用理由": "需要人工确认", "人工确认状态": "待确认", "是否影响筛选结果": "否（身份不参与本轮数值筛选）"})
            if len(选择CID) != 1:
                基础["匹配状态"] = "待人工确认" if len(选择CID) > 1 else "未找到"
                基础["自动匹配或人工确认"] = "人工确认"
                基础["冲突说明"] = "多个CID" if len(选择CID) > 1 else "PubChem未返回CID"
                if len(选择CID) > 1:
                    冲突.append({**基础, "冲突类型": "一个查询返回多个CID", "来源值一": 查询方式, "来源值二": str(选择CID), "当前采用值": "未自动采用", "采用理由": "多结构不可自动选择", "人工确认状态": "待确认", "是否影响筛选结果": "否（身份不参与本轮数值筛选）"})
                return 基础 | self._形式标记(名称, ""), 冲突
            属性 = self._获取属性(选择CID[0])
            SMILES = str(属性.get("IsomericSMILES", 属性.get("ConnectivitySMILES", "")))
            基础.update({"PubChem CID": str(选择CID[0]), "PubChem标准名称": str(属性.get("IUPACName", "")), "Isomeric SMILES": SMILES, "Canonical SMILES": str(属性.get("CanonicalSMILES", 属性.get("ConnectivitySMILES", ""))), "InChI": str(属性.get("InChI", "")), "InChIKey": str(属性.get("InChIKey", "")), "分子式": str(属性.get("MolecularFormula", "")), "匹配状态": "已匹配"})
            标准名 = re.sub(r"[^a-z0-9]", "", 名称.lower())
            返回名 = re.sub(r"[^a-z0-9]", "", 基础["PubChem标准名称"].lower())
            if 标准名 and 标准名 not in 返回名 and 返回名 not in 标准名:
                基础["冲突说明"] = "CAS/名称与返回标准名称可能为同义命名，需审核"
                冲突.append({**基础, "冲突类型": "CAS与返回名称明显不一致或同义待核对", "来源值一": 名称, "来源值二": 基础["PubChem标准名称"], "当前采用值": str(选择CID[0]), "采用理由": "CAS优先查询返回唯一CID", "人工确认状态": "待确认", "是否影响筛选结果": "否（身份不参与本轮数值筛选）"})
            return 基础 | self._形式标记(名称 + " " + 基础["PubChem标准名称"], SMILES), 冲突
        except Exception as 错误:
            基础.update({"匹配状态": "查询失败", "冲突说明": f"{type(错误).__name__}: {错误}"})
            return 基础 | self._形式标记(名称, ""), 冲突

    def 执行(self, 数据上下文: dict[str, Any]) -> pd.DataFrame:
        数据管理器 = 数据上下文["数据管理器"]
        输入标识 = 数据上下文.get("身份输入标识", "用户导入_统一候选记录")
        输出标识 = 数据上下文.get("身份输出标识", "化合物身份映射")
        输入 = 数据管理器.读取中间结果(输入标识).copy()
        if "数值初筛通过" in 输入.columns:
            输入 = 输入[输入["数值初筛通过"].astype(str).str.lower().eq("true")].copy()
        try:
            缓存 = 数据管理器.读取软件数据库表格(self.缓存文件)
        except FileNotFoundError:
            缓存 = pd.DataFrame()
        缓存键 = {}
        if not 缓存.empty:
            for _, 行 in 缓存.iterrows():
                记录 = 行.to_dict()
                for 键 in [self._缓存主键(记录), f"InChIKey:{str(记录.get('InChIKey', '') or '').strip()}"]:
                    if not 键.endswith(":"):
                        缓存键[键] = 记录
        try:
            旧结构缓存 = 数据管理器.读取软件数据库表格("补充数据2结构缓存.csv")
        except FileNotFoundError:
            旧结构缓存 = pd.DataFrame()
        旧结构键 = {str(行.get("CAS号", "")): 行.to_dict() for _, 行 in 旧结构缓存.iterrows()} if not 旧结构缓存.empty else {}
        批量属性 = {}
        if 旧结构键 and 数据上下文.get("允许网络身份查询"):
            try:
                批量属性 = self._批量获取属性([int(行["PubChem CID"]) for 行 in 旧结构键.values() if str(行.get("PubChem CID", "")).isdigit()])
            except Exception:
                批量属性 = {}
        记录, 冲突记录 = [], []
        for _, 行 in 输入.iterrows():
            输入键 = self._缓存主键({"原始CAS": 行.get("原始CAS", 行.get("论文_CAS号", "")), "InChIKey": 行.get("InChIKey", ""), "原始名称": 行.get("原始名称", 行.get("论文_化学名称", "")), "原始文件": 行.get("原始文件", ""), "候选编号": 行["候选编号"]})
            缓存值 = 缓存键.get(输入键)
            if 缓存值:
                记录.append(缓存值 | {"候选编号": str(行["候选编号"]), "原始名称": str(行.get("原始名称", 行.get("论文_化学名称", "")))})
                continue
            CAS = str(行.get("原始CAS", 行.get("论文_CAS号", "")))
            旧 = 旧结构键.get(CAS)
            属性 = 批量属性.get(str(旧.get("PubChem CID", ""))) if 旧 else None
            if 属性:
                名称 = str(行.get("原始名称", 行.get("论文_化学名称", "")))
                SMILES = str(属性.get("IsomericSMILES", 属性.get("ConnectivitySMILES", 属性.get("SMILES", ""))))
                身份 = {"候选编号": str(行["候选编号"]), "原始名称": 名称, "原始CAS": CAS, "原始货号": str(行.get("原始货号", 行.get("论文_货号", ""))), "查询方式": "CAS（既有PubChem缓存批量补全）", "PubChem CID": str(属性["CID"]), "PubChem标准名称": str(属性.get("IUPACName", 旧.get("PubChem返回名称", ""))), "Isomeric SMILES": SMILES, "Canonical SMILES": str(属性.get("CanonicalSMILES", 属性.get("ConnectivitySMILES", 属性.get("SMILES", "")))), "InChI": str(属性.get("InChI", "")), "InChIKey": str(属性.get("InChIKey", "")), "分子式": str(属性.get("MolecularFormula", "")), "查询来源": "PubChem PUG REST（复用CAS结构缓存）", "查询时间": datetime.now(timezone.utc).isoformat(), "匹配状态": "已匹配", "冲突说明": "", "自动匹配或人工确认": "自动匹配"} | self._形式标记(名称, SMILES)
                记录.append(身份)
                continue
            if 旧:
                名称 = str(行.get("原始名称", 行.get("论文_化学名称", "")))
                SMILES = str(旧.get("SMILES", ""))
                身份 = {"候选编号": str(行["候选编号"]), "原始名称": 名称, "原始CAS": CAS, "原始货号": str(行.get("原始货号", 行.get("论文_货号", ""))), "查询方式": "CAS（既有PubChem结构缓存）", "PubChem CID": str(旧.get("PubChem CID", "")), "PubChem标准名称": str(旧.get("PubChem返回名称", "")), "Isomeric SMILES": SMILES, "Canonical SMILES": SMILES, "InChI": "", "InChIKey": "", "分子式": "", "查询来源": "PubChem PUG REST（离线缓存）", "查询时间": str(旧.get("查询时间", "")), "匹配状态": "已匹配（缓存字段待补全）", "冲突说明": "", "自动匹配或人工确认": "自动匹配"} | self._形式标记(名称, SMILES)
                记录.append(身份)
                continue
            if not 数据上下文.get("允许网络身份查询"):
                记录.append({"候选编号": str(行["候选编号"]), "原始名称": str(行.get("原始名称", 行.get("论文_化学名称", ""))), "原始CAS": CAS, "原始货号": str(行.get("原始货号", 行.get("论文_货号", ""))), "查询方式": "未查询", "PubChem CID": "", "PubChem标准名称": "", "Isomeric SMILES": "", "Canonical SMILES": "", "InChI": "", "InChIKey": "", "分子式": "", "查询来源": "", "查询时间": "", "匹配状态": "尚未查询", "冲突说明": "网络查询未启用", "自动匹配或人工确认": "人工确认"} | self._形式标记("", ""))
                continue
            身份, 冲突 = self._转换一条(行)
            记录.append(身份); 冲突记录.extend(冲突)
        结果 = pd.DataFrame(记录)
        # “已匹配（缓存字段待补全）”仍是可复用的已确认身份，不能误报为冲突。
        待确认 = ~结果["匹配状态"].astype(str).str.startswith("已匹配")
        for _, 行 in 结果[待确认].iterrows():
            冲突记录.append({**行.to_dict(), "冲突类型": "待人工确认或查询失败", "来源值一": 行.get("原始CAS", ""), "来源值二": 行.get("冲突说明", ""), "当前采用值": "未自动采用", "采用理由": "身份不确定时禁止自动选择结构", "人工确认状态": "待确认", "是否影响筛选结果": "否（身份不参与本轮数值筛选）"})
        结果["缓存主键"] = 结果.apply(self._缓存主键, axis=1)
        合并缓存 = pd.concat([缓存, 结果], ignore_index=True) if not 缓存.empty else 结果.copy()
        合并缓存["缓存主键"] = 合并缓存.apply(self._缓存主键, axis=1)
        合并缓存 = 合并缓存.drop_duplicates(subset=["缓存主键"], keep="last")
        数据管理器.保存软件数据库表格(self.缓存文件, 合并缓存)
        数据管理器.保存中间结果(输出标识, 结果)
        数据管理器.保存筛选结果(self.冲突标识, pd.DataFrame(冲突记录))
        return 结果

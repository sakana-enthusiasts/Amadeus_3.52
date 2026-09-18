"""对补充数据3真实候选计算 RDKit 描述符并保存长表结果。"""

from typing import Any

import pandas as pd
from rdkit import Chem, rdBase
from rdkit.Chem import Crippen, Descriptors, Lipinski, rdMolDescriptors

from 插件.插件接口 import 基础插件接口


class RDKit普通描述符插件(基础插件接口):
    插件标识 = "RDKit普通描述符"
    输入标识 = "补充数据3_结构映射结果"
    输出标识 = "补充数据3_RDKit描述符结果"
    工具版本 = rdBase.rdkitVersion

    官能团模式 = {
        "羟基": "[OX2H]",
        "羧酸": "C(=O)[OX2H1]",
        "胺基": "[NX3;H1,H2]",
        "肼基": "[NX3][NX3]",
        "卤素": "[F,Cl,Br,I]",
        "含硼基团": "[B]",
    }
    Fig1c分类SMARTS = {
        "Alcohol": "[OX2H][CX4;!$(C=O)]", "Sugar": "[C;R]([OX2H])[C;R]([OX2H])",
        "Ether": "[OD2]([#6])[#6]", "Carboxyl": "C(=O)[OX2H1]", "Primary amine": "[NX3;H2][#6]",
        "Secondary amine": "[NX3;H1]([#6])[#6]", "Tertiary amine": "[NX3;H0]([#6])([#6])[#6]",
        "Amide": "C(=O)N", "Urea": "N-C(=O)-N", "Nitrile": "C#N", "Aromatic": "a",
        "Phenyl": "c1ccccc1", "Pyridine": "n1ccccc1", "Sulfur": "[S]", "Halogen": "[F,Cl,Br,I]",
    }

    def _Fig1c标签(self, 分子: Chem.Mol) -> dict[str, str]:
        return {f"功能基团_{名称}": "是" if 分子.HasSubstructMatch(Chem.MolFromSmarts(模式)) else "否" for 名称, 模式 in self.Fig1c分类SMARTS.items()} | {"功能基团识别规则": "; ".join(f"{名称}:{模式}" for 名称, 模式 in self.Fig1c分类SMARTS.items()), "功能基团_RDKit版本": self.工具版本, "功能基团是否人工确认": "否"}

    def _基础官能团(self, 分子: Chem.Mol) -> str:
        已识别 = []
        for 名称, smarts in self.官能团模式.items():
            模式 = Chem.MolFromSmarts(smarts)
            数量 = len(分子.GetSubstructMatches(模式)) if 模式 is not None else 0
            if 数量:
                已识别.append(f"{名称}:{数量}")
        return "; ".join(已识别) if 已识别 else "未识别基础官能团"

    def _描述符值(self, 分子: Chem.Mol) -> dict[str, float | int | str]:
        return {
            "分子量": round(Descriptors.MolWt(分子), 6),
            "脂水分配指标_MolLogP": round(Crippen.MolLogP(分子), 6),
            "极性表面积_TPSA": round(rdMolDescriptors.CalcTPSA(分子), 6),
            "氢键供体数": int(Lipinski.NumHDonors(分子)),
            "氢键受体数": int(Lipinski.NumHAcceptors(分子)),
            "芳香环数量": int(Lipinski.NumAromaticRings(分子)),
            "可旋转键数量": int(Lipinski.NumRotatableBonds(分子)),
            "芳香性": int(any(原子.GetIsAromatic() for 原子 in 分子.GetAtoms())),
            "基础官能团": self._基础官能团(分子),
        }

    def 执行(self, 数据上下文: dict[str, Any]) -> pd.DataFrame:
        数据管理器 = 数据上下文["数据管理器"]
        输入标识 = "补充数据2_结构映射结果" if 数据上下文.get("补充数据2描述符处理") else self.输入标识
        输出标识 = "补充数据2_RDKit描述符结果" if 数据上下文.get("补充数据2描述符处理") else self.输出标识
        if 数据上下文.get("用户描述符处理"):
            输入标识, 输出标识 = "用户导入_结构映射结果", "用户导入_RDKit描述符结果"
        候选表 = 数据管理器.读取中间结果(输入标识)
        结果记录: list[dict[str, Any]] = []
        for _, 行 in 候选表.iterrows():
            基础信息 = {
                "候选编号": 行["候选编号"],
                "候选名称": 行.get("论文_化学名称", 行.get("原始名称", "")),
                "CAS号": 行.get("论文_CAS号", 行.get("原始CAS", "")),
                "结构来源": 行.get("结构映射_来源", ""),
                "计算工具": "RDKit",
                "工具版本": self.工具版本,
            }
            SMILES = str(行.get("结构映射_SMILES", "") or "").strip()
            分子 = Chem.MolFromSmiles(SMILES) if SMILES else None
            if 分子 is None:
                原因 = str(行.get("结构错误信息", "SMILES 缺失或无效"))
                for 描述符名称 in self._描述符值(Chem.MolFromSmiles("O")).keys():
                    结果记录.append({**基础信息, "描述符名称": 描述符名称, "数值": None, "是否计算成功": False, "失败原因": 原因})
                continue
            for 描述符名称, 数值 in (self._描述符值(分子) | self._Fig1c标签(分子)).items():
                结果记录.append({**基础信息, "描述符名称": 描述符名称, "数值": 数值, "是否计算成功": True, "失败原因": ""})
        结果 = pd.DataFrame(结果记录)
        数据管理器.保存中间结果(输出标识, 结果)
        return 结果

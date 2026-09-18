"""离线、可追溯的公开纯组分数据快照；不是颅骨适用性白名单。"""

from copy import deepcopy
from 插件.配方物性.黏度.Cheng_2008 import 纯水黏度, 纯甘油黏度

FISHER = "https://www.fishersci.com/content/dam/fishersci/en_US/documents/programs/scientific/brochures-and-catalogs/brochures/fisher-chemical-chemicals-analytical-techniques-chromatography-brochure.pdf"
CHENG = "https://doi.org/10.1021/ie071349z"
WATER_RI = "https://atago-brazil.com/QandA_hsr.html"
WATER_RHO = "https://cdn.ncwm.com/userfiles/files/Meetings/Interim/Pub%2015%20Archive/2022/3-LR-Agenda_Master.pdf"


def _液体(编号, 名称, CAS, mw, rho, ri, eta, 来源, 说明=""):
    return {"物质编号": 编号, "化学名称": 名称, "CAS": CAS, "分子量_g_mol": mw,
            "相态": "液体", "密度_g_mL": rho, "密度温度_C": 20,
            "纯物质RI": ri, "RI温度_C": 20, "RI波长_nm": 589.3,
            "纯物质黏度_mPa_s": eta, "黏度温度_C": 20,
            "范特霍夫因子": 1, "因子来源": "理想非电解质假设，不是实测",
            "数据来源": 来源, "数据说明": 说明, "来源类型": "独立公开物性", "快照版本": "2026-09-13"}


def 公开水数据():
    return _液体("water", "水", "7732-18-5", 18.01528, .9982, 1.3330, 纯水黏度(20),
               {"密度": WATER_RHO, "RI": WATER_RI, "黏度": CHENG}, "纯水黏度为Cheng经验式值；输入误差未量化")


def 甘油验证数据():
    return _液体("glycerol", "甘油", "56-81-5", 92.094, 1.261, 1.4746, 纯甘油黏度(20),
        {"密度": "https://www.sigmaaldrich.com/BT/en/product/mm/104095",
         "RI": "https://labchem-wako.fujifilm.com/europe/product/detail/W01W0107-0063.html",
         "RI波长佐证": "https://juser.fz-juelich.de/record/858615/files/Schluesseltech_188.pdf?subformat=pdfa",
         "黏度": CHENG}, "純甘油黏度为Cheng经验式值；不是实验实测标签") | {"来源类型": "验证专用"}


def 公开物性演示库():
    # 固定独立来源快照。不得从论文表格、验证配置或论文排序导出此池。
    return deepcopy([
        公开水数据(),
        _液体("dmso", "二甲基亚砜", "67-68-5", 78.13, 1.10, 1.479, 2.24,
            {"密度和RI": "https://www.merckmillipore.com/AZ/en/product/sial/01934", "黏度": FISHER},
            "密度取供应商20°C规格区间中点；黏度来自Fisher表20°C列，非25°C RI/密度列"),
        _液体("acetone", "丙酮", "67-64-1", 58.08, .791, 1.359, .36,
            {"密度和RI": "https://b2b.sigmaaldrich.com/US/en/product/sigald/24201", "黏度": FISHER},
            "密度取20°C规格区间中点；供应商常数不代表当前批次实测"),
        _液体("ipa", "异丙醇", "67-63-0", 60.10, .785, 1.377, 2.40,
            {"密度和RI": "https://www.sigmaaldrich.com/DE/de/product/mm/59300m", "黏度": FISHER},
            "供应商标称物性；混溶性、组织毒理及模型外推误差未验证"),
    ])


def 默认发现配置():
    return {"最小组分数": 1, "最大组分数": 3, "最大配方数": 2000,
            "粗搜步长百分比": 20, "细化步长百分比": 5, "优化轮数": 2,
            "返回数量": 8, "目标折射率": 1.56,
            "物性条件": {"温度_C": 20, "波长_nm": 589.3},
            "扩散探针": {"名称": "假设1nm标准探针", "半径_nm": 1,
                         "来源": "演示配置明确指定，用于横向比较；不是候选分子的真实半径"}}

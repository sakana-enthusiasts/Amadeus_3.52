"""对当前搜索产生的前沿做质量转移局部细化；不使用已知配方作种子。"""

from 插件.插件接口 import 基础插件接口
from math import isclose, isfinite
from .自动组合插件 import 组装定义


def 组成签名(定义):
    return tuple(sorted((x["物质编号"], round(x["用量"], 10)) for x in 定义["组分"]))


class 比例优化插件(基础插件接口):
    插件标识 = "配方比例局部优化"

    def 执行(self, 数据上下文):
        配置 = 数据上下文["生成配置"]
        步长 = 配置.get("细化步长百分比", 5)
        if isinstance(步长, bool) or 步长 not in {1, 2, 5, 10} or 步长 >= 配置.get("粗搜步长百分比", 20):
            raise ValueError("细化步长须为1、2、5或10质量百分点，且小于粗搜步长")
        库 = {x["物质编号"]: x for x in 数据上下文["物质库"]}
        已见 = set(数据上下文["已有签名"])
        输出 = []
        for 配方 in 数据上下文["当前前沿"]:
            原始 = {x["成分键"]: x["质量分数"] for x in 配方["成分"]}
            if (not 原始 or any(isinstance(f, bool) or not isinstance(f, (int, float))
                    or not isfinite(f) or f <= 0 for f in 原始.values())
                    or not isclose(sum(原始.values()), 1, abs_tol=1e-6, rel_tol=0)):
                raise ValueError("局部细化必须使用已组装的规范化质量组成")
            for a in sorted(原始):
                for b in sorted(原始):
                    if a == b or 原始[a] <= 步长/100 + 1e-9:
                        continue
                    组成 = 原始 | {a: 原始[a]-步长/100, b: 原始[b]+步长/100}
                    定义 = 组装定义(组成, 库, 配置)
                    签名 = 组成签名(定义)
                    if 签名 in 已见:
                        continue
                    已见.add(签名)
                    定义["优化来源"] = 配方["配方编号"]
                    输出.append(定义)
        return 输出

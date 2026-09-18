"""本地研发命令入口；不联网、不发布，输出只写运行记录。"""

import argparse
from datetime import datetime
import json
from pathlib import Path
from uuid import uuid4

from 核心系统.配方研发流程 import 运行验证模式, 运行发现模式
from 设置.公开物性样例 import 公开物性演示库, 默认发现配置
from 核心系统.目标规格 import load_profile


def 主程序():
    p = argparse.ArgumentParser(description="Amadeus：独立配方发现与已知体系验证")
    p.add_argument("模式", choices=["验证", "发现"])
    p.add_argument("--候选库", type=Path, help="独立来源物质记录JSON；发现模式无默认候选")
    p.add_argument("--约束", type=Path)
    p.add_argument("--配置", type=Path)
    p.add_argument("--target-profile", type=Path, help="Target Profile 1.0 JSON；仅发现模式")
    p.add_argument("--试跑演示库", action="store_true", help="仅明确启用时加载供应商演示数据")
    p.add_argument("--最少组分", type=int)
    args = p.parse_args()
    if args.模式 == "验证" and args.target_profile:
        p.error("--target-profile 仅用于发现模式")
    读取 = lambda path: json.loads(path.read_text(encoding="utf-8-sig"))
    if args.模式 == "验证":
        r = 运行验证模式()
        配方们 = [x["预测"] for x in r["体系"]]
        说明 = "已知体系复现与缺失项诊断；不表示新体系或生物安全验证通过。"
    else:
        if bool(args.候选库) == args.试跑演示库:
            p.error("发现模式须指定 --候选库 或显式 --试跑演示库，不能同时指定")
        库 = 读取(args.候选库) if args.候选库 else 公开物性演示库()
        配置 = 默认发现配置() | (读取(args.配置) if args.配置 else {})
        if args.最少组分 is not None:
            配置["最小组分数"] = args.最少组分
        r = 运行发现模式(库, 配置, 约束=读取(args.约束) if args.约束 else None,
                       目标规格=load_profile(args.target_profile) if args.target_profile else None)
        配方们 = r["候选"]
        说明 = f"{r['状态']}；计算{r['生成数量']}个配方，返回{len(配方们)}个。主体自动选择；Benchmark只在排序完成后读取。"
    目录 = Path(__file__).resolve().parent / "运行记录" / ("配方研发_" + datetime.now().strftime("%Y%m%d_%H%M%S_") + uuid4().hex[:6])
    目录.mkdir(parents=True)
    (目录/"完整结果.json").write_text(json.dumps(r, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    行 = ["# Amadeus 配方研发本地试跑", "", 说明, "", "预测区间均未量化；未知毒理不能当成低毒。", ""]
    if args.模式 == "发现":
        行 += ["粗搜、局部细化与约束：", "", "```json", json.dumps({k:r.get(k) for k in ("粗搜数量","优化记录","约束","排序规则")}, ensure_ascii=False, indent=2), "```", ""]
    for i, 配方 in enumerate(配方们, 1):
        行 += [f"## {i}. {配方['配方名称']}", "", 配方.get("推荐原因", "已知基准体系，未参与发现排序"), "",
               "|成分|角色|质量分数|摩尔分数|等效体积分数|", "|---|---|---:|---:|---:|"]
        格式 = lambda v: "缺失" if v is None else f"{v:.6g}"
        for x in 配方["成分"]:
            行.append(f"|{x['化学名称']}|{x['配方角色']}|{格式(x['质量分数'])}|{格式(x['摩尔分数'])}|{格式(x['体积分数'])}|")
        行 += ["", "|指标|预测值|单位|模型|不确定度|", "|---|---:|---|---|---|"]
        for k,v in 配方["配方物性"].items():
            行.append(f"|{k}|{格式(v['值'])}|{v['单位']}|{v['方法']}|{v['不确定度说明']}|")
        行 += ["", "缺失数据：" + "；".join(配方["缺失数据"]), "", "体积依据：" + 配方["体积依据"], ""]
    行 += ["完整输入、来源、模型警告、约束和最后文献对照见同目录的完整结果.json。"]
    (目录/"试跑报告.md").write_text("\n".join(行), encoding="utf-8")
    print(说明)
    print(目录/"试跑报告.md")


if __name__ == "__main__":
    主程序()

"""依据共用数据层的真实结果生成可展示、可下载的筛选图表。"""

from datetime import datetime
import json
from pathlib import Path
from typing import Any

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager
import pandas as pd

from 插件.插件接口 import 基础插件接口


class 筛选结果图表插件(基础插件接口):
    插件标识 = "筛选结果图表"
    筛选统计标识 = "补充数据2_规则筛选步骤统计"
    统一记录标识 = "补充数据2_规则筛选统一记录"
    图表目录名 = "图表"
    规则版本 = "SeeThrough补充数据2数值规则 v1"

    @staticmethod
    def _配置中文字体() -> None:
        字体路径 = Path("C:/Windows/Fonts/simhei.ttf")
        if 字体路径.is_file():
            font_manager.fontManager.addfont(str(字体路径))
        plt.rcParams["font.family"] = "SimHei"
        plt.rcParams["font.sans-serif"] = ["SimHei", "Microsoft YaHei", "DejaVu Sans"]
        plt.rcParams["axes.unicode_minus"] = False

    @staticmethod
    def _写图(fig: plt.Figure, PNG路径: Path, SVG路径: Path) -> None:
        PNG路径.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(PNG路径, dpi=300, bbox_inches="tight", facecolor="white")
        fig.savefig(SVG路径, format="svg", bbox_inches="tight", facecolor="white")
        plt.close(fig)

    def _读取真实数据(self, 数据管理器: Any) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
        统计 = 数据管理器.读取中间结果(self.筛选统计标识).copy()
        记录 = 数据管理器.读取筛选结果(self.统一记录标识).copy()
        自动候选 = 记录[记录["自动规则通过"].astype(str).str.lower().eq("true")].copy()
        if 自动候选.empty:
            raise ValueError("当前没有自动规则通过的候选，无法生成筛选结果图表。")
        if len(统计) != 5 or 140 in pd.to_numeric(统计["剩余数量"], errors="coerce").dropna().tolist():
            raise ValueError("筛选统计不是5步软件自动计算链，或混入了论文约140对照数据。")
        return 统计, 记录, 自动候选

    @staticmethod
    def _数量链(统计: pd.DataFrame) -> tuple[list[str], list[int]]:
        规则名 = ["清理后真实候选"] + 统计["筛选步骤"].astype(str).tolist()
        数量 = [int(pd.to_numeric(统计.iloc[0]["筛选前数量"], errors="raise"))] + pd.to_numeric(统计["剩余数量"], errors="raise").astype(int).tolist()
        return 规则名, 数量

    def _生成数量变化图(self, 统计: pd.DataFrame, 自动候选: pd.DataFrame, 目录: Path) -> tuple[Path, Path]:
        步骤, 数量 = self._数量链(统计)
        fig, ax = plt.subplots(figsize=(10, 6.2))
        颜色 = ["#2A6F97"] * (len(数量) - 1) + ["#C64B3B"]
        柱 = ax.bar(range(len(数量)), 数量, color=颜色, width=0.66)
        ax.set_title("SeeThrough候选试剂自动筛选结果", fontsize=17, weight="bold", pad=16)
        ax.set_ylabel("候选数量")
        ax.set_xticks(range(len(步骤)), [名称.replace("与BA的", "与BA\n的").replace("水合评分不低于-1.5", "水合评分\n≥ -1.5") for 名称 in 步骤], rotation=0)
        ax.grid(axis="y", alpha=0.18)
        ax.spines[["top", "right"]].set_visible(False)
        for 图柱, 数值 in zip(柱, 数量):
            ax.text(图柱.get_x() + 图柱.get_width() / 2, 数值 + max(数量) * 0.018, str(数值), ha="center", va="bottom", fontsize=11, weight="bold")
        最终10 = int(自动候选.get("论文最终10候选标签", pd.Series(dtype=str)).eq("是").sum())
        人工核查比例 = len(自动候选) / 数量[0] * 100
        ax.text(0.98, 0.97, f"初始候选：{数量[0]}\n最终自动候选：{len(自动候选)}\n论文最终10恢复：{最终10}/10\n最终人工核查范围：{人工核查比例:.2f}%", transform=ax.transAxes, ha="right", va="top", fontsize=11, bbox={"boxstyle": "round,pad=0.5", "facecolor": "#F3F7FA", "edgecolor": "#9FB3C8"})
        ax.text(0.5, -0.25, "注：论文报告“约140个芳香候选”仅为方法对照，不属于软件自动筛选步骤。", transform=ax.transAxes, ha="center", fontsize=9, color="#555555")
        fig.tight_layout()
        PNG路径, SVG路径 = 目录 / "候选试剂筛选数量变化图.png", 目录 / "候选试剂筛选数量变化图.svg"
        self._写图(fig, PNG路径, SVG路径)
        return PNG路径, SVG路径

    def _生成分布图(self, 自动候选: pd.DataFrame, 目录: Path) -> tuple[Path, Path]:
        数据 = 自动候选.copy()
        for 列 in ["汉森距离_与BA", "论文_eRI"]:
            数据[列] = pd.to_numeric(数据[列], errors="coerce")
        fig, ax = plt.subplots(figsize=(9.2, 6.4))
        标签 = 数据.get("论文最终10候选标签", pd.Series("否", index=数据.index)).eq("是")
        论文 = 数据[标签]
        额外 = 数据[~标签]
        ax.scatter(额外["汉森距离_与BA"], 额外["论文_eRI"], s=70, color="#4F8FB3", label="自动额外10", alpha=0.9, edgecolors="white", linewidths=0.7)
        ax.scatter(论文["汉森距离_与BA"], 论文["论文_eRI"], s=78, color="#D05A4E", label="论文最终10（事后对照）", alpha=0.95, edgecolors="white", linewidths=0.7)
        # Antipyrine 在补充数据2中以系统名“2,3-Dimethyl-1-phenyl-5-pyrazolone”记录；仅用于图中注释，不参与任何筛选。
        需标注 = 数据[数据["论文_化学名称"].astype(str).str.contains("Antipyrine|Dimethyl-1-phenyl-5-pyrazolone", case=False, na=False, regex=True)]
        for _, 行 in 需标注.iterrows():
            ax.annotate("Antipyrine", (行["汉森距离_与BA"], 行["论文_eRI"]), xytext=(7, 7), textcoords="offset points", fontsize=10, weight="bold")
        ax.axvline(10, linestyle="--", color="#9A9A9A", linewidth=1, label="Ra(BA) 阈值=10")
        ax.set_title("自动筛选候选的物化参数分布", fontsize=16, weight="bold", pad=14)
        ax.set_xlabel("与BA的Hansen距离 Ra")
        ax.set_ylabel("估算折射率 eRI")
        ax.grid(alpha=0.2)
        ax.spines[["top", "right"]].set_visible(False)
        ax.legend(frameon=False, loc="best")
        fig.tight_layout()
        PNG路径, SVG路径 = 目录 / "最终候选物化参数分布图.png", 目录 / "最终候选物化参数分布图.svg"
        self._写图(fig, PNG路径, SVG路径)
        return PNG路径, SVG路径

    def 执行(self, 数据上下文: dict[str, Any]) -> dict[str, Path]:
        数据管理器 = 数据上下文["数据管理器"]
        self._配置中文字体()
        统计, _, 自动候选 = self._读取真实数据(数据管理器)
        目录 = 数据管理器.导出结果目录 / self.图表目录名
        数量PNG, 数量SVG = self._生成数量变化图(统计, 自动候选, 目录)
        分布PNG, 分布SVG = self._生成分布图(自动候选, 目录)
        步骤, 数量 = self._数量链(统计)
        元数据 = {"生成时间": datetime.now().isoformat(timespec="seconds"), "使用的数据文件": [f"数据/中间结果/{self.筛选统计标识}.csv", f"数据/筛选结果/{self.统一记录标识}.csv"], "使用的规则版本": self.规则版本, "当前筛选阈值": {"水合评分": ">= -1.5", "水合能力": "> BA", "eRI": "> 1.58", "Ra(BA)": "< 10"}, "软件真实计算链": dict(zip(步骤, 数量)), "自动候选数": len(自动候选), "论文最终10恢复数": int(自动候选["论文最终10候选标签"].eq("是").sum()), "说明": "论文约140个芳香候选只作方法对照，未进入自动计算链。"}
        元数据路径 = 目录 / "筛选结果图表元数据.json"
        元数据路径.write_text(json.dumps(元数据, ensure_ascii=False, indent=2), encoding="utf-8")
        return {"数量图PNG": 数量PNG, "数量图SVG": 数量SVG, "分布图PNG": 分布PNG, "分布图SVG": 分布SVG, "元数据": 元数据路径}

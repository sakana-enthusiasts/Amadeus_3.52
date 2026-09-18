"""稳定指标元数据；不查询数据、不预测、不依赖插件。"""

from dataclasses import asdict, dataclass
from types import MappingProxyType


@dataclass(frozen=True)
class MetricBinding:
    metric_id: str
    scope: str
    source: str
    field: str
    unit: str
    executable: bool = True
    evidence_types: tuple[str, ...] = ("measured", "predicted")
    roles: tuple[str, ...] = ("hard_constraint", "objective", "report_only")

    def to_dict(self):
        return asdict(self)


METRIC_BINDINGS = MappingProxyType({b.metric_id: b for b in (
    MetricBinding("refractive_index", "formulation", "配方物性", "混合折射率", ""),
    MetricBinding("viscosity", "formulation", "配方物性", "混合黏度", "mPa·s"),
    MetricBinding("diffusion_coefficient", "formulation", "配方物性", "溶液自由扩散系数", "m²/s"),
    MetricBinding("osmotic_pressure", "formulation", "配方物性", "渗透压", "Pa"),
    MetricBinding("water_activity", "formulation", "配方物性", "水活度", ""),
    MetricBinding("cost", "formulation", "配方结果", "成本_元_kg", "元/kg",
                  evidence_types=("derived",)),
    MetricBinding("molecular_weight", "molecule", "物质记录", "分子量_g_mol", "g/mol",
                  evidence_types=("unspecified",), roles=("hard_constraint", "report_only")),
)})

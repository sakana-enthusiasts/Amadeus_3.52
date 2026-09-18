# Target Profile 1.0

`核心系统/目标规格/` 提供独立规格契约、严格校验、不可变编辑与 JSON 持久化。它不导入插件、workflow、候选库、实验数据、Benchmark 或模型设置；不触发自动注册、启动调度、读取数据库或联网。

Execution v1 已从 `运行发现模式(..., 目标规格=profile)` 与 CLI `--target-profile` 接入现有发现流程、分子筛选、约束评价、唯一 Pareto 排序和局部再评价。未接 UI 或全面公开证据层。指标绑定仅声明稳定字段/单位/来源能力；执行计划仅编译/预检，跨模块调度仍在核心研发流程。

## 中性 JSON 示例

```json
{
  "name": "formulation_screen_v1",
  "target_profile_version": "1.0",
  "criteria": {
    "refractive_index": {
      "role": "objective",
      "scope": "formulation",
      "mode": "target",
      "target": 1.50,
      "tolerance": 0.02,
      "missing_policy": "keep_unknown",
      "evidence_requirement": "measured_or_predicted"
    },
    "viscosity": {
      "role": "objective",
      "scope": "formulation",
      "mode": "minimize",
      "missing_policy": "keep_unknown"
    },
    "molecular_weight": {
      "role": "hard_constraint",
      "scope": "molecule",
      "upper": 500,
      "unit": "g/mol",
      "missing_policy": "exclude"
    },
    "cost": {"role": "report_only", "missing_policy": "keep_unknown"},
    "density": {"role": "disabled", "scope": "formulation"}
  }
}
```

数值仅演示格式，不是经过验证的用途规格或默认搜索需求。名称不参与候选生成、评价或打分，规格不含候选清单、CAS/SMILES、成功标签或 Benchmark。

## 字段与实际校验

- 顶层只接受且必填 name、target_profile_version、criteria；仅支持版本字符串 `1.0`，不自动迁移。
- criteria 是小写 snake_case 指标 ID 到 Criterion 的映射，允许空映射作草稿和扩展 ID；当前不判断该指标是否已有模型，也不允许重名指标。
- scope 允许 molecule/formulation/delivery/experiment；可省略，保持未指定。delivery 是代码允许的通用作用域，不代表当前已有递送模块或递送指标实现。
- 可选字段应省略，不接受 JSON 显式 null。拒绝未知字段、重复键、非法枚举、布尔数值、数值字符串、NaN、Infinity 和溢出数值。
- 启用指标省略 missing_policy 时规范化为 keep_unknown，省略 evidence_requirement 时为 any；这些是配置默认语义，不是填充候选实验数据。
- unit 必须是非空字符串，校验层不推断量纲、不检查单位兼容或换算。没有 weight 或加权总分字段。

| role | 当前配置要求 | 语义与执行边界 |
| --- | --- | --- |
| hard_constraint | 至少 lower/upper 或布尔 equals，二者互斥 | 沿用现有约束路径；当前数值绑定不支持布尔 equals，预检明确失败 |
| objective | 必填 mode | 变换为最小化向量，沿用唯一 Pareto 排序 |
| report_only | 不接受目标/阈值，只允许 keep_unknown | 采集值和未知原因，不影响资格或向量 |
| disabled | 只接受 role 和可选 scope | 不进入执行要求、淘汰或排序，不额外调度模型 |

上下限包含边界且 lower≤upper。equals 只接受布尔值，不能嵌入候选名称或标签。report_only+exclude 是矛盾配置，校验报错。

| objective mode | 字段契约与规格语义 |
| --- | --- |
| minimize/maximize | 不接受 target/tolerance/lower/upper；表达越小/越大越优 |
| target | 必须 target 和非负 tolerance，不接受 lower/upper；表达容差带目标 |
| range | 必须 lower/upper 且有序，不接受 target/tolerance；表达可接受区间 |

目标容差/区间不等于硬约束。minimize 使用 value，maximize 使用 -value，target 使用 abs(value-target)，range 在区间内为 0、外部为距最近边界的距离。tolerance 保留在规格与结果，不自动淘汰远目标候选。

## 缺失与证据要求

keep_unknown 保留未知，hard_constraint 显示未知不伪装通过；objective 保留在未知未排序候选及全部评价中，不进入 Pareto。exclude 在缺合格值时取消资格。report_only 永远不取消资格。缺失不填零、均值或惩罚大数。legacy 与规格硬约束分别保留来源、取 AND，直接冲突预检报错；有 Profile objectives 时优先，否则沿用 legacy 目标与默认 RI+黏度。

| evidence_requirement | 规格含义 |
| --- | --- |
| measured_only | 只接受实测 |
| measured_or_predicted | 可接受二者，可比条件下优先实测 |
| predicted_allowed | 可接受二者，不额外强制实测优先，不是仅预测 |
| any | 不以类别作门槛，但仍需保留值、单位、来源、条件和未知状态 |

本模块不查询或选择公开证据，不把 summary 当 measured。执行适配检查现有物性结果的状态/来源/原始单位，并保留条件；数据来源缺失不能自动满足 any。预检逐项检查绑定、scope、执行来源、单位、role、证据能力与 legacy 冲突，失败在自检和组合搜索之前返回。

## Execution v1 支持清单

| metric_id | scope | 当前值来源 | 标准单位 | role |
| --- | --- | --- | --- | --- |
| refractive_index | formulation | 配方物性.混合折射率 | 无量纲，结果 unit 为空串，规格省略 unit | hard_constraint/objective/report_only |
| viscosity | formulation | 配方物性.混合黏度 | mPa·s | 同上 |
| diffusion_coefficient | formulation | 配方物性.溶液自由扩散系数 | m²/s | 同上 |
| osmotic_pressure | formulation | 配方物性.渗透压 | Pa | 同上 |
| water_activity | formulation | 配方物性.水活度 | 无量纲，规格省略 unit | 同上 |
| cost | formulation | 配方约束评价结果.成本_元_kg | 元/kg | 同上；derived，仅 any |
| molecular_weight | molecule | 物质记录.分子量_g_mol | g/mol | hard_constraint/report_only；来源类型未细分，仅 any |

五类物性可区分 measured/predicted，当前发现入口没有配方实测输入，measured_only 预检失败；measured_or_predicted/predicted_allowed/any 可接现有预测。目标只要求其实际需要的合格值，不再固定要求 RI+黏度。原完整物性预测保持，规格不因 disabled 增加计算要求，未建立选择性模型调度框架。

未绑定指标（如 water_solubility、pKa、logD、toxicity）、delivery/experiment、分子目标聚合和布尔 equals 当前 unsupported；不伪造模型。显式单位必须与绑定一致，无换算框架。公开证据全面连接、UI、ADMET、HSP Sphere、结构搜索仍未实现，当前没有 Agent。

发现结果保留 Target Profile 原始快照/version、ExecutionPlan、预检及最终实际 objectives；全部配方和排除分子的 criterion 记录含原始值/单位、合格值、来源/类型/条件、状态/缺失原因、role、硬判断或目标变换/向量。report_only 已在现有完整预测和约束评价后采集，最终结果汇总；Benchmark 在所有搜索和排序之后加载。

## Python 接口与持久化

```python
from 核心系统.目标规格 import (
    Criterion, TargetProfile, import_profile_json, export_profile_json,
    save_profile, load_profile,
)

profile = TargetProfile("formulation_screen_v1", {})
profile = profile.with_criterion("refractive_index", Criterion(
    role="objective", scope="formulation", mode="target",
    target=1.50, tolerance=0.02,
    evidence_requirement="measured_or_predicted",
))
edited = profile.renamed("formulation_screen_v2")
text = export_profile_json(edited)
assert import_profile_json(text) == edited

# 路径由调用方明确选择，父目录已经存在：
# save_profile(edited, user_selected_path)
# restored = load_profile(user_selected_path)
# save_profile(edited, user_selected_path, overwrite=True)
```

Criterion/TargetProfile 不可变，编辑返回新对象，构造/导入/编辑均校验，to_dict 返回独立副本。JSON 稳定排序、UTF-8，导入兼容 BOM；规范化可加入显式策略，但往返语义一致。

没有默认路径，不把 name 拼成目录，也不创建父目录。只保存 `.json`，默认拒覆盖；显式 overwrite 时在目标目录临时写入并原子替换，失败清理临时文件。内部 JSON 解析辅助函数和临时路径不是其他模块的接口。

## 扩展与验证边界

新增通用指标 ID 可通过现有 Criterion/TargetProfile 表达，不创建平行规格模型。仅有 ID 不代表对应模型存在；不得用研究概念或规格名称自动生成软件需求。

现有配置测试验证严格契约、JSON 往返、不可变编辑、失败保存、独立导入无写入/联网。执行回归使用内存/tmp_path 验证 disabled 要求隔离、hard constraints、四种目标变换、多目标 Pareto、缺失/证据策略、report_only 隔离、legacy 兼容、CLI 与 Benchmark 最后读取。TD-01 已同步修复，局部质量组成回归和绝对投料兼容测试通过，见 [07](../07_技术债与遗留预留.md)。

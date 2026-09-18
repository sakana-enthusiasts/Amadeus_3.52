"""仅内存/tmp_path；不调用真实数据写入入口。"""

from copy import deepcopy
import json
import sys

import pytest

from 核心系统.目标规格 import Criterion, TargetProfile, save_profile
from 核心系统.目标规格.执行计划 import compile_profile
from 核心系统.配方研发流程 import 运行发现模式
from 插件.配方生成.发现约束插件 import 配方约束评价插件, 候选分子筛选插件
from 插件.配方生成.候选排序插件 import 配方候选排序插件


def profile(**criteria):
    return TargetProfile("execution_test", {k: Criterion.from_dict(v) for k, v in criteria.items()})


def plan(p, **kwargs):
    result, check = compile_profile(p, **kwargs)
    assert check["passed"], check
    return result


def pool():
    return [{"物质编号": i, "化学名称": i, "CAS": cas, "分子量_g_mol": mw,
             "来源类型": "用户独立输入", "数据来源": "合成测试",
             "相态": "液体", "密度_g_mL": 1, "密度温度_C": 20,
             "纯物质RI": ri, "RI温度_C": 20, "RI波长_nm": 589.3,
             "纯物质黏度_mPa_s": eta, "黏度温度_C": 20,
             "范特霍夫因子": 1, "价格_元_kg": price}
            for i, cas, mw, ri, eta, price in [("a", "7732-18-5", 18, 1.33, 1, 10),
                                            ("b", "test-b", 100, 1.5, 5, 20)]]


def config():
    return {"物性条件": {"温度_C": 20, "波长_nm": 589.3}, "目标折射率": 1.45,
            "粗搜步长百分比": 20, "细化步长百分比": 5, "优化轮数": 1,
            "最小组分数": 2, "最大组分数": 2, "最大配方数": 100,
            "扩散探针": {"名称": "测试", "半径_nm": 1, "来源": "合成输入"}}


def formulation(identifier, **values):
    return {"配方编号": identifier, "成分": [{"成分键": "a", "质量分数": 1,
              "价格_元_kg": 10, "数据来源": "测试"}], "配方定义": {"组分": [
              {"物质编号": "a", "用量": 1}]}, "物性条件": {"温度_C": 20},
            "配方物性": {k: {"值": v, "单位": unit, "状态": "已预测",
                           "数据来源": "测试模型", "条件": {"温度_C": 20}}
                         for k, (v, unit) in values.items()}}


def evaluate(f, execution, legacy=None):
    return f | 配方约束评价插件().执行({"配方": f, "执行计划": execution, "约束": legacy or {}})


def sort(fs, execution):
    return 配方候选排序插件().执行({"预测配方": [evaluate(f, execution) for f in fs],
                                  "执行计划": execution, "返回数量": 8})


def test_disabled未绑定也不进入执行要求():
    p = profile(unimplemented={"role": "disabled", "scope": "delivery"})
    execution = plan(p)
    assert not execution.criteria and not execution.objectives
    assert execution.to_dict()["required_metrics"] == []


@pytest.mark.parametrize("metric,criterion,reason", [
    ("water_solubility", {"role": "report_only", "scope": "molecule"}, "未绑定"),
    ("viscosity", {"role": "objective", "mode": "minimize", "scope": "molecule"}, "scope"),
    ("viscosity", {"role": "report_only", "unit": "Pa·s"}, "unit"),
    ("cost", {"role": "report_only", "evidence_requirement": "measured_only"}, "evidence_requirement"),
    ("molecular_weight", {"role": "report_only", "evidence_requirement": "predicted_allowed"}, "evidence_requirement"),
    ("refractive_index", {"role": "report_only", "evidence_requirement": "measured_only"}, "evidence_requirement"),
    ("viscosity", {"role": "hard_constraint", "equals": True}, "equals"),
    ("molecular_weight", {"role": "objective", "mode": "minimize"}, "role"),
    ("delivery_rate", {"role": "report_only", "scope": "delivery"}, "未绑定"),
    ("experiment_result", {"role": "report_only", "scope": "experiment"}, "未绑定"),
])
def test_预检明确失败(metric, criterion, reason):
    _, check = compile_profile(profile(**{metric: criterion}))
    assert not check["passed"]
    assert reason in str(check)


def test_运行来源不可用():
    p = profile(viscosity={"role": "objective", "mode": "minimize"})
    assert not compile_profile(p, available_properties=[])[1]["passed"]
    assert not compile_profile(p, model_selection={"混合黏度": "measured_only"})[1]["passed"]


@pytest.mark.parametrize("mode,fields,values,expected", [
    ("minimize", {}, [1, 2], [1, 2]),
    ("maximize", {}, [1, 2], [-1, -2]),
    ("target", {"target": 3, "tolerance": 0}, [1, 3, 4], [2, 0, 1]),
    ("range", {"lower": 2, "upper": 4}, [1, 2, 3, 4, 6], [1, 0, 0, 0, 2]),
])
def test_objective方向和变换(mode, fields, values, expected):
    execution = plan(profile(viscosity={"role": "objective", "mode": mode, **fields}))
    fs = [formulation(str(i), 混合黏度=(v, "mPa·s")) for i, v in enumerate(values)]
    result = sort(fs, execution)
    assert result["排序总数"] == len(values)  # objective 距目标远仍可参与。
    by_id = {f["配方编号"]: f for f in result["候选"]}
    for i, v in enumerate(expected):
        assert by_id[str(i)]["objective向量"] == [v]
        assert by_id[str(i)]["目标规格评价"][0]["objective value"] == v
    assert result["候选"][0]["objective向量"] == [min(expected)]


def test_两个目标沿用Pareto且稳定编号():
    execution = plan(profile(viscosity={"role": "objective", "mode": "minimize"},
                             water_activity={"role": "objective", "mode": "maximize"}))
    fs = [formulation(i, 混合黏度=(eta, "mPa·s"), 水活度=(aw, ""))
          for i, eta, aw in [("b", 1, .2), ("a", 1, .2), ("c", 2, .8), ("d", 3, .1)]]
    r = sort(fs, execution)
    assert [f["配方编号"] for f in r["候选"]] == ["a", "b", "c", "d"]
    assert [f["非支配层"] for f in r["候选"]] == [1, 1, 1, 2]
    assert r == sort(list(reversed(fs)), execution)


def test_report_only缺失不能影响约束排序():
    execution = plan(profile(viscosity={"role": "objective", "mode": "minimize"},
                             refractive_index={"role": "report_only"}))
    f = formulation("a", 混合黏度=(2, "mPa·s"))
    r = sort([f], execution)
    assert r["排序总数"] == 1
    assert r["候选"][0]["实际排序objectives"] == ["viscosity"]
    record = next(x for x in r["候选"][0]["目标规格评价"] if x["role"] == "report_only")
    assert record["状态"] == "unknown" and record["缺失原因"]
    assert r["候选"][0]["可参与排序"]


@pytest.mark.parametrize("policy", ["keep_unknown", "exclude"])
def test_缺失objective不填数值(policy):
    execution = plan(profile(viscosity={"role": "objective", "mode": "minimize", "missing_policy": policy}))
    r = sort([formulation("a")], execution)
    assert not r["候选"] and not r["Pareto前沿"]
    assert r["排除"][0]["状态"] == ("excluded" if policy == "exclude" else "unknown_unranked")
    assert bool(r["未知未排序候选"]) == (policy == "keep_unknown")
    assert r["排除"][0]["配方"]["目标规格评价"][0]["合格值"] is None
    fs = [evaluate(formulation("b"), execution)]
    ctx = {"预测配方": fs, "执行计划": execution, "返回数量": 8}
    sorter = 配方候选排序插件()
    assert sorter.执行(ctx) == sorter.执行(ctx)


@pytest.mark.parametrize("policy,allowed", [("keep_unknown", True), ("exclude", False)])
def test_硬约束未知策略(policy, allowed):
    execution = plan(profile(viscosity={"role": "hard_constraint", "upper": 2, "missing_policy": policy}))
    r = evaluate(formulation("a"), execution)
    assert r["可参与排序"] is allowed
    assert r["目标规格评价"][0]["hard_constraint判断"] == "未知"


def test_硬约束边界AND且保留来源():
    execution = plan(profile(viscosity={"role": "hard_constraint", "lower": 2, "upper": 5}))
    for v, allowed in [(1, False), (2, True), (5, True), (6, False)]:
        r = evaluate(formulation("a", 混合黏度=(v, "mPa·s")), execution)
        assert r["可参与排序"] is allowed
    r = evaluate(formulation("a", 混合黏度=(4, "mPa·s")), execution,
                 {"物性约束": {"混合黏度": {"最大": 3}}})
    assert not r["可参与排序"]
    assert {x["来源"] for x in r["约束检查"]} == {"legacy", "Target Profile"}


@pytest.mark.parametrize("metric,criterion,legacy", [
    ("viscosity", {"role": "hard_constraint", "lower": 5}, {"物性约束": {"混合黏度": {"最大": 4}}}),
    ("cost", {"role": "hard_constraint", "lower": 5}, {"成本上限_元_kg": 4}),
    ("molecular_weight", {"role": "hard_constraint", "upper": 5}, {"分子约束": {"分子量_g_mol": {"最小": 6}}}),
])
def test_直接冲突预检报错(metric, criterion, legacy):
    assert "直接冲突" in str(compile_profile(profile(**{metric: criterion}), legacy_constraints=legacy)[1])


def test_legacy数值字符串范围仍兼容():
    p = profile(viscosity={"role": "hard_constraint", "lower": 2})
    assert compile_profile(p, legacy_constraints={"物性约束": {"混合黏度": {"最大": "3"}}})[1]["passed"]
    assert not compile_profile(p, legacy_constraints={"物性约束": {"混合黏度": {"最大": "1"}}})[1]["passed"]


def test_分子约束先筛候选():
    execution = plan(profile(molecular_weight={"role": "hard_constraint", "upper": 50, "scope": "molecule"}))
    r = 候选分子筛选插件().执行({"物质库": pool(), "执行计划": execution})
    assert [x["物质编号"] for x in r["物质库"]] == ["a"]
    assert r["排除分子"][0]["目标规格评价"][0]["hard_constraint判断"] == "不满足"


def test_证据状态来源单位不得伪装合格():
    execution = plan(profile(viscosity={"role": "objective", "mode": "minimize"}))
    for change in [{"状态": "summary"}, {"数据来源": ""}, {"单位": "Pa·s"}]:
        f = formulation("a", 混合黏度=(2, "mPa·s"))
        f["配方物性"]["混合黏度"].update(change)
        assert not sort([f], execution)["候选"]


def test_预检失败先于模型组合Benchmark(monkeypatch):
    import 核心系统.配方研发流程 as flow
    def fail(*args, **kwargs):
        pytest.fail("失败预检不应启动计算")
    monkeypatch.setattr(flow, "运行数值自检", fail)
    monkeypatch.setattr(flow, "运行验证模式", fail)
    r = 运行发现模式(pool(), config(), 目标规格=profile(unknown={"role": "report_only"}))
    assert r["生成数量"] == 0 and not r["执行预检"]["passed"]


def test_流程真实接入及Benchmark最后读取(monkeypatch):
    import 核心系统.配方研发流程 as flow
    events = []
    original = flow.配方候选排序插件.执行
    def ranked(self, ctx):
        events.append("sort")
        return original(self, ctx)
    def benchmark(**kwargs):
        assert events and events[-1] == "sort"
        events.append("benchmark")
        return {"体系": [], "待补文献协议": []}
    monkeypatch.setattr(flow.配方候选排序插件, "执行", ranked)
    monkeypatch.setattr(flow, "运行验证模式", benchmark)
    p = profile(viscosity={"role": "objective", "mode": "maximize"},
                cost={"role": "report_only"}, molecular_weight={"role": "report_only"})
    cfg = config()
    cfg.pop("目标折射率")
    snapshot = deepcopy(pool())
    r = 运行发现模式(snapshot, cfg, 目标规格=p, 模型选择={"混合折射率": "measured_only"},
                    约束={"优化目标": {"混合黏度": "最小"}})
    assert events[-1] == "benchmark"
    assert r["执行预检"]["passed"] and r["候选"] and not r["组装失败"]
    assert r["最终排序objectives"] == ["viscosity"]
    assert r["Target Profile快照"] == p.to_dict()
    assert r["Target Profile version"] == "1.0"
    assert snapshot == pool()
    assert all(x["配方物性"]["混合折射率"]["值"] is None for x in r["候选"])
    assert len(r["全部配方评价"]) > r["粗搜数量"]
    json.dumps(r, allow_nan=False)


def test_无Profile及无Profile目标均保留legacy(monkeypatch):
    import 核心系统.配方研发流程 as flow
    monkeypatch.setattr(flow, "运行验证模式", lambda **kwargs: {"体系": [], "待补文献协议": []})
    old = 运行发现模式(pool(), config())
    p = profile(cost={"role": "report_only"})
    new = 运行发现模式(pool(), config(), 目标规格=p)
    assert [x["配方编号"] for x in new["候选"]] == [x["配方编号"] for x in old["候选"]]
    assert new["最终排序objectives"] == ["RI目标差", "混合黏度"]
    assert not old["组装失败"]


def test_CLI正式JSON读取且所有报告位于tmp_path(tmp_path, monkeypatch):
    import 运行配方研发 as cli
    import 核心系统.配方研发流程 as flow
    monkeypatch.setattr(flow, "运行验证模式", lambda **kwargs: {"体系": [], "待补文献协议": []})
    candidate = tmp_path / "pool.json"
    candidate.write_text(json.dumps(pool()), encoding="utf-8")
    settings = tmp_path / "config.json"
    settings.write_text(json.dumps(config()), encoding="utf-8")
    target = save_profile(profile(cost={"role": "objective", "mode": "minimize"}), tmp_path / "profile.json")
    monkeypatch.setattr(cli, "__file__", str(tmp_path / "运行配方研发.py"))
    monkeypatch.setattr(sys, "argv", ["cli", "发现", "--候选库", str(candidate), "--配置", str(settings),
                                      "--target-profile", str(target)])
    cli.主程序()
    output = list((tmp_path / "运行记录").glob("*/完整结果.json"))
    assert len(output) == 1
    assert json.loads(output[0].read_text(encoding="utf-8"))["最终排序objectives"] == ["cost"]


@pytest.mark.parametrize("metric", ["refractive_index", "viscosity", "diffusion_coefficient",
                                    "osmotic_pressure", "water_activity", "cost"])
def test_每个formulation绑定真实执行且单位一致(metric, monkeypatch):
    import 核心系统.配方研发流程 as flow
    monkeypatch.setattr(flow, "运行验证模式", lambda **kwargs: {"体系": [], "待补文献协议": []})
    p = profile(**{metric: {"role": "objective", "mode": "minimize"}})
    r = 运行发现模式(pool(), config(), 目标规格=p)
    assert r["执行预检"]["passed"] and r["排序总数"] == r["生成数量"]
    assert not r["组装失败"]
    for f in r["候选"]:
        record = next(x for x in f["目标规格评价"] if x["metric_id"] == metric)
        assert record["合格值"] is not None
        assert record["原始单位"] == record["标准单位"]


def test_report_only运行时缺失不影响自检或排序(monkeypatch):
    import 核心系统.配方研发流程 as flow
    from 插件.配方物性.配方物性汇总 import 创建默认模型注册表
    from 插件.配方物性.黏度.接口 import 黏度模型接口
    from 插件.配方物性.配方物性接口 import 输入不可用

    class 缺失模型(黏度模型接口):
        方法 = "missing_test"

        def 预测(self, 配方, 上游):
            raise 输入不可用("合成模型缺失")

    registry = 创建默认模型注册表()
    registry.注册(缺失模型())
    monkeypatch.setattr(flow, "运行验证模式", lambda **kwargs: {"体系": [], "待补文献协议": []})
    p = profile(cost={"role": "objective", "mode": "minimize"}, viscosity={"role": "report_only"})
    r = 运行发现模式(pool(), config(), 目标规格=p, 注册表=registry, 模型选择={"混合黏度": "missing_test"})
    assert r["执行预检"]["passed"] and r["数值自检"]["通过"]
    assert r["排序总数"] == r["生成数量"]
    assert all(x["可参与排序"] for x in r["全部配方评价"])


def test_发现无新增联网并记录disabled(monkeypatch):
    import socket
    import 核心系统.配方研发流程 as flow
    def fail(*args, **kwargs):
        pytest.fail("发现不应联网")
    monkeypatch.setattr(socket.socket, "connect", fail)
    monkeypatch.setattr(socket, "create_connection", fail)
    monkeypatch.setattr(flow, "运行验证模式", lambda **kwargs: {"体系": [], "待补文献协议": []})
    p = profile(cost={"role": "objective", "mode": "minimize"}, future={"role": "disabled"})
    r = 运行发现模式(pool(), config(), 目标规格=p)
    assert r["候选"]
    assert all(next(x for x in f["目标规格评价"] if x["metric_id"] == "future")["状态"] == "disabled"
               for f in r["全部配方评价"])

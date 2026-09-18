"""第一步只验证配置契约与隔离；不冒充尚未接入的执行层测试。"""

from copy import deepcopy
from dataclasses import FrozenInstanceError
import json
from pathlib import Path
import subprocess
import sys

import pytest

from 核心系统.目标规格 import (
    Criterion, ProfileValidationError, TargetProfile,
    export_profile_json, import_profile_json, load_profile, save_profile,
)


def example():
    return {
        "name": "injection_skull_clearing_v1", "target_profile_version": "1.0",
        "criteria": {
            "refractive_index": {"role": "objective", "mode": "target", "target": 1.56,
                                 "tolerance": .02, "missing_policy": "keep_unknown"},
            "viscosity": {"role": "objective", "mode": "minimize", "missing_policy": "keep_unknown"},
            "toxicity": {"role": "report_only", "missing_policy": "keep_unknown"},
            "systemic_pk": {"role": "disabled"},
        },
    }


def test_用户原始JSON兼容且不修改输入():
    source = example()
    snapshot = deepcopy(source)
    profile = TargetProfile.from_dict(source)
    assert source == snapshot
    assert profile.criteria["refractive_index"].scope is None
    assert profile.criteria["viscosity"].evidence_requirement == "any"
    assert profile.criteria["systemic_pk"].to_dict() == {"role": "disabled"}


@pytest.mark.parametrize("criterion", [
    {"role": "disabled", "scope": "delivery"},
    {"role": "report_only"},
    {"role": "hard_constraint", "lower": 10, "unit": "g/L"},
    {"role": "hard_constraint", "upper": 100},
    {"role": "hard_constraint", "lower": 0, "upper": 0},
    {"role": "hard_constraint", "equals": False},
    {"role": "objective", "mode": "minimize"},
    {"role": "objective", "mode": "maximize"},
    {"role": "objective", "mode": "target", "target": 1.56, "tolerance": 0},
    {"role": "objective", "mode": "range", "lower": 1.54, "upper": 1.58},
])
def test_四角色和目标模式往返(criterion):
    p = TargetProfile("example", {"metric": Criterion.from_dict(criterion)})
    assert import_profile_json(export_profile_json(p)) == p


@pytest.mark.parametrize("scope", ["molecule", "formulation", "delivery", "experiment"])
@pytest.mark.parametrize("evidence", ["measured_only", "measured_or_predicted", "predicted_allowed", "any"])
@pytest.mark.parametrize("policy", ["keep_unknown", "exclude"])
def test_缺失策略作用域证据要求均被保留(scope, evidence, policy):
    c = Criterion(role="objective", mode="minimize", scope=scope,
                  evidence_requirement=evidence, missing_policy=policy)
    assert Criterion.from_dict(c.to_dict()) == c


@pytest.mark.parametrize("bad", [
    {"role": "unknown"}, {"role": True}, {"role": []},
    {"role": "report_only", "scope": "unknown"},
    {"role": "report_only", "missing_policy": "assume_pass"},
    {"role": "report_only", "evidence_requirement": "unknown"},
    {"role": "report_only", "missing_policy": "exclude"},
    {"role": "report_only", "lower": 0},
    {"role": "disabled", "mode": "minimize"},
    {"role": "disabled", "missing_policy": "exclude"},
    {"role": "disabled", "evidence_requirement": "any"},
    {"role": "disabled", "scope": None},
    {"role": "objective"}, {"role": "objective", "mode": "weighted_sum"},
    {"role": "objective", "mode": "minimize", "target": 1},
    {"role": "objective", "mode": "maximize", "equals": True},
    {"role": "objective", "mode": "target", "target": 1.56},
    {"role": "objective", "mode": "target", "target": 1.56, "tolerance": -.02},
    {"role": "objective", "mode": "target", "target": 1.56, "tolerance": .02, "lower": 1},
    {"role": "objective", "mode": "range", "lower": 1},
    {"role": "objective", "mode": "range", "lower": 2, "upper": 1},
    {"role": "hard_constraint"},
    {"role": "hard_constraint", "lower": 0, "equals": False},
    {"role": "hard_constraint", "equals": "Antipyrine"},
    {"role": "hard_constraint", "equals": 1},
    {"role": "hard_constraint", "lower": 0, "mode": "minimize"},
    {"role": "hard_constraint", "lower": 0, "unit": ""},
    {"role": "hard_constraint", "lower": 0, "unit": {}},
    {"role": "objective", "mode": "minimize", "weight": .5},
    {"role": "report_only", "candidate_names": ["Antipyrine"]},
    {"role": "report_only", "benchmark_label": "success"},
    {"role": "report_only", "model_parameters": {}},
])
def test_矛盾和非法配置拒绝(bad):
    with pytest.raises(ProfileValidationError):
        Criterion.from_dict(bad)


@pytest.mark.parametrize("value", [True, "1.56", float("nan"), float("inf"), -float("inf"), 10**400])
def test_数值字段不做隐式填充或转换(value):
    with pytest.raises(ProfileValidationError):
        Criterion(role="objective", mode="target", target=value, tolerance=.02)


@pytest.mark.parametrize("text", [
    '{"name":"a","name":"b","target_profile_version":"1.0","criteria":{}}',
    '{"name":"a","target_profile_version":"1.0","criteria":{"x":{"role":"disabled","role":"report_only"}}}',
    '{"name":"a","target_profile_version":"1.0","criteria":{"x":{"role":"hard_constraint","lower":NaN}}}',
    '{"name":"a","target_profile_version":"1.0","criteria":{"x":{"role":"hard_constraint","lower":Infinity}}}',
    '{"name":"a","target_profile_version":"1.0","criteria":{"x":{"role":"hard_constraint","lower":1e999}}}',
    'null', '[]', '{broken}',
])
def test_JSON错误和重复键拒绝(text):
    with pytest.raises(ProfileValidationError):
        import_profile_json(text)


@pytest.mark.parametrize("key", ["candidate_pool", "CAS", "SMILES", "benchmark_labels", "experimental_data", "model_parameters"])
def test_不能将其他模块数据嵌入规格(key):
    data = example() | {key: ["known_success"]}
    with pytest.raises(ProfileValidationError):
        TargetProfile.from_dict(data)


@pytest.mark.parametrize("change", [
    {"name": " "}, {"name": []}, {"target_profile_version": "2.0"},
    {"criteria": []}, {"criteria": {"60-80-0": {"role": "disabled"}}},
    {"criteria": {"C1=CC=CC=C1": {"role": "disabled"}}},
])
def test_顶层和指标ID校验(change):
    with pytest.raises(ProfileValidationError):
        TargetProfile.from_dict(example() | change)


def test_新建编辑不会改变原对象或输入字典():
    criteria = {}
    original = TargetProfile("new", criteria)
    criteria["toxicity"] = Criterion("report_only")
    assert dict(original.criteria) == {}
    edited = original.with_criterion("systemic_pk", Criterion("disabled")).renamed("edited")
    assert original.name == "new" and not original.criteria
    assert edited.without_criterion("systemic_pk") == TargetProfile("edited", {})
    with pytest.raises(TypeError):
        edited.criteria["toxicity"] = Criterion("report_only")
    with pytest.raises(FrozenInstanceError):
        edited.criteria["systemic_pk"].role = "objective"
    output = edited.to_dict()
    output["criteria"]["systemic_pk"]["role"] = "report_only"
    assert edited.criteria["systemic_pk"].role == "disabled"
    with pytest.raises(ProfileValidationError):
        edited.with_criterion("new_metric", {"role": "disabled"})


def test_JSON文件往返与编辑保存(tmp_path):
    original = TargetProfile.from_dict(example()).renamed("局部透明化目标规格")
    target = tmp_path / "profile.json"
    assert save_profile(original, target) == target
    assert load_profile(target) == original
    assert import_profile_json("\ufeff" + export_profile_json(original)) == original
    assert export_profile_json(load_profile(target)) == target.read_text(encoding="utf-8")
    edited = original.with_criterion("toxicity", Criterion("disabled"))
    with pytest.raises(FileExistsError):
        save_profile(edited, target)
    assert load_profile(target) == original
    save_profile(edited, target, overwrite=True)
    assert load_profile(target) == edited
    assert list(tmp_path.iterdir()) == [target]


def test_失败存取不创建目录或破坏旧文件(tmp_path, monkeypatch):
    p = TargetProfile("empty", {})
    with pytest.raises(FileNotFoundError):
        save_profile(p, tmp_path / "new_directory" / "profile.json")
    assert not (tmp_path / "new_directory").exists()
    with pytest.raises(ProfileValidationError):
        save_profile(p, tmp_path / "profile.csv")
    target = save_profile(p, tmp_path / "profile.json")
    old_bytes = target.read_bytes()
    import 核心系统.目标规格.JSON存取 as io
    def fail(*args):
        raise OSError("模拟原子替换失败")
    monkeypatch.setattr(io.os, "replace", fail)
    with pytest.raises(OSError):
        save_profile(p.renamed("changed"), target, overwrite=True)
    assert target.read_bytes() == old_bytes
    assert list(tmp_path.iterdir()) == [target]


def test_独立导入不启动旧流程不写文件():
    # 独立解释器保证模块没有被 pytest 的其他导入预先缓存。
    code = '''
import sys
class BlockOtherProjectModules:
    def find_spec(self, fullname, path=None, target=None):
        if (fullname.startswith(("插件", "设置", "软件界面")) or
            (fullname.startswith("核心系统.") and not fullname.startswith("核心系统.目标规格"))):
            raise AssertionError("不应加载旧流程: " + fullname)
sys.meta_path.insert(0, BlockOtherProjectModules())
def audit(event, args):
    if event in {"os.mkdir", "os.remove", "os.rename", "socket.connect"}:
        raise AssertionError("不应触发副作用: " + event)
    if event == "open" and isinstance(args[1], str) and any(x in args[1] for x in "wax+"):
        raise AssertionError("不应写文件")
sys.addaudithook(audit)
from 核心系统.目标规格 import TargetProfile, Criterion, import_profile_json, export_profile_json
p = TargetProfile("isolated", {"systemic_pk": Criterion("disabled")})
assert import_profile_json(export_profile_json(p)) == p
'''
    result = subprocess.run([sys.executable, "-B", "-c", code],
                            cwd=Path(__file__).resolve().parents[1], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


def test_不带TargetProfile的旧发现流程在存取前后完全一致(tmp_path):
    from 核心系统.配方研发流程 import 运行发现模式
    from 设置.公开物性样例 import 公开物性演示库, 默认发现配置
    pool, config = 公开物性演示库(), 默认发现配置()
    snapshot_pool, snapshot_config = deepcopy(pool), deepcopy(config)
    before = 运行发现模式(pool, config)
    profile = TargetProfile.from_dict(example())
    save_profile(profile, tmp_path / "independent.json")
    assert load_profile(tmp_path / "independent.json") == profile
    after = 运行发现模式(pool, config)
    assert after == before
    assert pool == snapshot_pool and config == snapshot_config
    assert before["生成数量"] > before["粗搜数量"] == 52
    assert before["排序总数"] == before["生成数量"]
    assert len(before["候选"]) == 8
    assert not before["组装失败"]  # TD-01 已修复；存取仍不影响发现结果。

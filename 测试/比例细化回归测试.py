import pytest

from 插件.配方生成.自动组合插件 import 组装定义
from 插件.配方生成.比例优化插件 import 比例优化插件, 组成签名
from 插件.配方生成.配方输入组装插件 import 配方输入组装插件


def 输入():
    库 = [{"物质编号": i, "化学名称": i, "分子量_g_mol": 100,
           "相态": "液体", "密度_g_mL": 1, "密度温度_C": 20}
          for i in ("a", "b")]
    配置 = {"粗搜步长百分比": 20, "细化步长百分比": 5}
    return 库, 配置


def 组装(定义, 库):
    return 配方输入组装插件().执行({"配方定义": 定义, "物质库": 库,
                                  "物性条件": {"温度_C": 20}})


def test_20_80从规范化质量分数细化并重新组装():
    库, 配置 = 输入()
    定义 = 组装定义({"a": .2, "b": .8}, {x["物质编号"]: x for x in 库}, 配置)
    配方 = 组装(定义, 库)
    assert [x["用量"] for x in 配方["配方定义"]["组分"]] == [20, 80]
    新 = 比例优化插件().执行({"生成配置": 配置, "物质库": 库,
          "已有签名": {组成签名(定义)}, "当前前沿": [配方]})
    assert sorted(x["组分"][0]["用量"] for x in 新) == pytest.approx([.15, .25])
    for x in 新:
        assert sum(c["用量"] for c in x["组分"]) == pytest.approx(1)
        assert all(c["用量"] > 0 and c["单位"] == "质量分数" for c in x["组分"])
        assert sum(c["质量分数"] for c in 组装(x, 库)["成分"]) == pytest.approx(1)


def test_转移不产生零或负比例():
    库, 配置 = 输入()
    定义 = 组装定义({"a": .05, "b": .95}, {x["物质编号"]: x for x in 库}, 配置)
    新 = 比例优化插件().执行({"生成配置": 配置, "物质库": 库,
          "已有签名": set(), "当前前沿": [组装(定义, 库)]})
    assert len(新) == 1
    assert 新[0]["组分"][0]["用量"] == pytest.approx(.1)


@pytest.mark.parametrize("unit", ["g", "mL"])
def test_绝对输入验证保持合法(unit):
    库, 配置 = 输入()
    定义 = 组装定义({"a": .2, "b": .8}, {x["物质编号"]: x for x in 库}, 配置)
    for c, amount in zip(定义["组分"], [20, 80]):
        c.update(单位=unit, 用量=amount)
    assert [c["质量分数"] for c in 组装(定义, 库)["成分"]] == pytest.approx([.2, .8])


@pytest.mark.parametrize("bad", [0, -.1, float("nan")])
def test_非法细化输入拒绝(bad):
    库, 配置 = 输入()
    with pytest.raises(ValueError, match="规范化"):
        比例优化插件().执行({"生成配置": 配置, "物质库": 库,
          "已有签名": set(), "当前前沿": [{"成分": [
              {"成分键": "a", "质量分数": bad}, {"成分键": "b", "质量分数": 1-bad}]}]})

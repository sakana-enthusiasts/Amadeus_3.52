"""旧页面/报告字段的边界转换；没有网络、缓存、选择或物性合并逻辑。"""

import json
import re

import pandas as pd


def format_ghs(evidence, raw_body=""):
    if not evidence:
        return {}
    items = list(evidence) if isinstance(evidence, (tuple, list)) else [evidence]
    texts = [t for e in items for t in e.value["statements"]]
    all_text = [t for e in items for t in e.value.get("annotation_text", e.value["statements"])]
    categories = [t for t in all_text if re.search(r"Acute Toxicity|Skin Corrosion|Eye Damage|Carcinogenicity|Reproductive Toxicity|Specific Target Organ|Flammable", t, re.I)]
    return {"H代码": "; ".join(sorted({c for e in items for c in e.value["codes"]})),
            "危险说明": " | ".join(dict.fromkeys(texts))[:3000],
            "信号词": "; ".join(sorted({s for e in items for s in e.value["signal_words"]})),
            "危险类别": " | ".join(dict.fromkeys(categories))[:2000], "报告比例": "; ".join(sorted({
                x for t in all_text for x in re.findall(r"\b\d+(?:\.\d+)?%", t)})),
            "提交来源": json.dumps([e.reference for e in items], ensure_ascii=False),
            "是否存在不同来源冲突": "未评估（多个H代码不代表冲突）", "原始响应": raw_body}


def candidates_for_legacy(context):
    if "公开毒理候选" in context:
        value = context["公开毒理候选"]
        return value.copy() if isinstance(value, pd.DataFrame) else pd.DataFrame(value or [])
    manager = context["数据管理器"]
    identity = manager.读取中间结果("补充数据2_41候选身份映射")
    screened = manager.读取筛选结果("补充数据2_规则筛选统一记录")
    selected = screened[screened["自动规则通过"].astype(str).str.lower().eq("true")][["候选编号", "论文_CAS号"]]
    return selected.merge(identity, on="候选编号", how="left", suffixes=("", "_身份"))


def save_legacy(context, rows, raw_cache):
    records, logs, responses = [], [], []
    for row, identity, result in rows:
        raw_id = result.raw_record_ids[-1] if result.raw_record_ids else ""
        raw = raw_cache.by_id(raw_id)
        values = format_ghs(result.evidence, raw.body if raw else "")
        cid = identity.identifiers.get("pubchem_cid", "")
        batch = {key: row.get(key, "") for key in ("批次编号", "来源运行编号", "确认清单标识")}
        status = "已查询" if values else "无GHS结果" if result.status == "not_found" else "查询失败"
        cache_hit = "是" if result.cache_hit else "否"
        record = {**batch, "候选编号": identity.compound_id, "化学名称": row.get("化学名称", row.get("原始名称", "")),
            "CAS": row.get("CAS", row.get("CAS号", row.get("论文_CAS号", row.get("原始CAS", "")))),
            "PubChem CID": cid, "InChIKey": identity.inchikey, "化合物形式": identity.chemical_form,
            "证据来源类型": "公开数据", "公开数据源": "PubChem GHS", "证据分类": "危险提示",
            "证据可参与条件匹配": False, "毒性终点": "GHS危险提示", "物种": "不适用", "细胞或组织来源": "不适用",
            "给药途径": "不适用", "剂量": "", "剂量单位": "", "暴露时长": "", "观察时长": "",
            "结果": values.get("危险说明") or result.message, "实验值或预测值": "数据库汇总",
            "原始数据、数据库汇总或模型预测": "数据库汇总", "数据来源": "PubChem PUG-View GHS Classification",
            "原始来源链接或编号": f"https://pubchem.ncbi.nlm.nih.gov/compound/{cid}" if cid else "",
            "可信度": "GHS危险提示；需追溯原始来源", "数据是否与当前实验条件匹配": "否/不适用",
            "备注": "不参与 A/B/C/D 条件匹配或自动淘汰", "查询方式": "确认身份或源内唯一身份解析",
            "查询状态": status, "缓存命中": cache_hit, **values}
        records.append(record)
        logs.append({**batch, "候选编号": identity.compound_id, "公开数据源": "PubChem GHS", "PubChem CID": cid,
                     "查询状态": status, "缓存命中": cache_hit, "查询时间": raw.retrieved_at if raw else "", "错误": result.message})
        if raw:
            responses.append({**batch, "候选编号": identity.compound_id, "公开数据源": "PubChem GHS", "PubChem CID": cid,
                              "查询时间": raw.retrieved_at, "原始响应": raw.body})
    table = pd.DataFrame(records)
    manager = context["数据管理器"]
    if "公开毒理候选" in context:
        manager.保存筛选结果("毒理公开证据_PubChemGHS", table)
        manager.保存筛选结果("毒理公开查询日志", pd.DataFrame(logs))
        manager.保存筛选结果("毒理公开原始响应_PubChemGHS", pd.DataFrame(responses))
    else:
        manager.保存中间结果("PubChem_GHS毒性证据", table)
    return table

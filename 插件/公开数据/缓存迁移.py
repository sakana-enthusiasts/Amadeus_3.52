"""旧 CSV 缓存只导入可核对的原始 JSON，不把旧宽表当成标准证据。"""

import json
from urllib.parse import quote


def import_legacy_ghs(manager, cache):
    try:
        table = manager.读取软件数据库表格("PubChem_GHS缓存.csv")
    except FileNotFoundError:
        return
    for row in table.to_dict("records"):
        cid = str(row.get("PubChem CID", ""))
        body = row.get("原始响应", "")
        if not cid.isdigit() or not isinstance(body, str) or not body:
            continue
        try:
            record = json.loads(body).get("Record", {})
            if not record or (record.get("RecordNumber") and str(record["RecordNumber"]) != cid):
                continue
            endpoint = f"https://pubchem.ncbi.nlm.nih.gov/rest/pug_view/data/compound/{cid}/JSON?heading={quote('GHS Classification', safe='')}"
            if cache.get("pubchem", endpoint, ignore_age=True) is None:
                cache.save("pubchem", endpoint, cid, 200, body, "legacy-ghs-csv-import",
                           retrieved_at=row.get("查询时间") or None)
        except (ValueError, TypeError):
            continue

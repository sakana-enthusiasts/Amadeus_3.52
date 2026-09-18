from 核心系统.公开证据.数据结构 import PropertyEvidence
from 核心系统.公开证据.单位标准化 import convert, normalize_evidence
from ..解析工具 import parse_conditions, parse_quantity
from .mapping import CHEMISTRY_MAP, COMPTOX_PROPERTY_MAP


PARSER_VERSION = "comptox-1.0"


def records(payload):
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        for key in ("content", "data", "results"):
            if isinstance(payload.get(key), list):
                return payload[key]
        return [payload] if payload else []
    raise ValueError("Unexpected CTX response shape")


class CTXParser:
    def parse(self, raw, identity, domain):
        result = []
        for index, record in enumerate(records(raw.json())):
            if record.get("dtxsid") and record["dtxsid"] != identity.identifiers["dtxsid"]:
                raise ValueError("CTX DTXSID does not match observed form")
            if identity.inchikey and record.get("inchikey") and record["inchikey"] != identity.inchikey:
                raise ValueError("CTX InChIKey conflicts with observed form")
            base = dict(compound_id=identity.compound_id, chemical_form=identity.chemical_form,
                        source="comptox", source_record_id=str(record.get("id", identity.identifiers["dtxsid"])),
                        retrieved_at=raw.retrieved_at, parser_version=PARSER_VERSION, raw_record_id=raw.raw_record_id,
                        observed_structure=identity.observed_structure or record.get("smiles", ""),
                        standardized_parent_structure=identity.standardized_parent_structure,
                        extra={"domain": domain, "record_index": index, "original_record": record})
            if domain == "chemistry":
                for field, property_id in CHEMISTRY_MAP.items():
                    if record.get(field):
                        result.append(PropertyEvidence(**base, property_id=property_id, value=record[field],
                                                      evidence_type="summary", method="DSSTox identity"))
                continue
            if domain in {"experimental", "predicted"}:
                name = record.get("propName", "")
                property_id = COMPTOX_PROPERTY_MAP.get(name, "comptox:" + name)
                value = record.get("propValue")
                unit = record.get("propUnit") or ""
                text = record.get("propValueOriginal") or record.get("propValueString") or record.get("propValueText") or ""
                qualifier = "="
                # 不用一个数字覆盖原始记录中的界限或范围。
                if text:
                    parsed, parsed_unit, parsed_qualifier = parse_quantity(text, unit, dimensionless=property_id in {"pKa", "logP", "refractive_index"})
                    if value is None or parsed_qualifier not in {"=", "text"}:
                        value, unit, qualifier = parsed, parsed_unit, parsed_qualifier
                if value is None:
                    continue
                conditions = parse_conditions(text)
                if record.get("expDetailsTemperatureC") is not None:
                    conditions["temperature"] = convert(record["expDetailsTemperatureC"], "°C")[0]
                if record.get("expDetailsPressureMmhg") is not None:
                    conditions["pressure"] = convert(record["expDetailsPressureMmhg"], "mmHg")[0]
                if record.get("expDetailsPh") is not None:
                    conditions["pH"] = record["expDetailsPh"]
                if property_id == "water_solubility":
                    conditions["solvent"] = "water"
                result.append(normalize_evidence(PropertyEvidence(**base, property_id=property_id, value=value,
                    unit=unit, qualifier=qualifier, evidence_type="measured" if domain == "experimental" else "predicted",
                    method=record.get("sourceName") or "", model_name=record.get("modelName") or "",
                    model_version=record.get("modelVersion") or "",
                    applicability_domain={k: v for k, v in record.items() if k.startswith("ad")},
                    reference={"citation": record.get("lsCitation"), "doi": record.get("lsDoi"),
                               "url": record.get("directUrl") or record.get("publicSourceUrl"), "qmrf": record.get("qmrfUrl")},
                    **conditions)))
            else:
                # 领域记录完整保留，未知毒理条件不伪造为可匹配的实验终点。
                result.append(PropertyEvidence(**base, property_id=f"{domain}_record", value=record,
                    evidence_type="summary", method=f"CTX {domain}", reference={"url": raw.endpoint}))
        return result

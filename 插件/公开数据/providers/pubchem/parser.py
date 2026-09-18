from dataclasses import replace
import re

from 核心系统.公开证据.数据结构 import PropertyEvidence
from 核心系统.公开证据.单位标准化 import normalize_evidence
from ..解析工具 import evidence_kind, parse_conditions, parse_quantity
from .mapping import DIMENSIONLESS, PUBCHEM_COMPUTED_MAP, PUBCHEM_PROPERTY_MAP


PARSER_VERSION = "pubchem-1.0"


def evidence_base(identity, raw):
    return dict(compound_id=identity.compound_id, chemical_form=identity.chemical_form,
                observed_structure=identity.observed_structure,
                standardized_parent_structure=identity.standardized_parent_structure,
                source="pubchem", source_record_id=identity.identifiers.get("pubchem_cid", ""),
                retrieved_at=raw.retrieved_at, parser_version=PARSER_VERSION, raw_record_id=raw.raw_record_id)


def sections(node, path=()):
    if isinstance(node, dict):
        current = path + ((node["TOCHeading"],) if "TOCHeading" in node else ())
        yield node, current
        for key, value in node.items():
            if key != "Information":
                yield from sections(value, current)
    elif isinstance(node, list):
        for item in node:
            yield from sections(item, path)


def text_values(node):
    if isinstance(node, dict):
        for key, value in node.items():
            if key == "String" and isinstance(value, str):
                yield value
            elif isinstance(value, (dict, list)):
                yield from text_values(value)
    elif isinstance(node, list):
        for item in node:
            yield from text_values(item)


class PUGRestParser:
    def parse(self, raw, identity):
        evidence = []
        for record in raw.json().get("PropertyTable", {}).get("Properties", []):
            if str(record.get("CID", "")) != identity.identifiers["pubchem_cid"]:
                raise ValueError("Returned CID does not match observed identity")
            key = record.get("InChIKey", "")
            if identity.inchikey and key and identity.inchikey != key:
                raise ValueError("Returned InChIKey does not match observed chemical form")
            for field, (property_id, unit) in PUBCHEM_COMPUTED_MAP.items():
                if record.get(field) is not None:
                    value = record[field]
                    if property_id == "molecular_weight":
                        value = float(value)
                    evidence.append(PropertyEvidence(**evidence_base(identity, raw), property_id=property_id,
                                    value=value, unit=unit, evidence_type="predicted", method="PubChem PUG REST computed property",
                                    model_name="PubChem", reference={"url": raw.endpoint}, extra={"source_field": field}))
        return evidence


class PUGViewParser:
    def discover(self, raw):
        return tuple(dict.fromkeys(node.get("TOCHeading") for node, path in sections(raw.json())
                     if "Experimental Properties" in path and node.get("TOCHeading") in PUBCHEM_PROPERTY_MAP))

    def parse(self, raw, identity, heading):
        record = raw.json().get("Record", {})
        if record.get("RecordNumber") and str(record["RecordNumber"]) != identity.identifiers["pubchem_cid"]:
            raise ValueError("Annotation RecordNumber does not match CID")
        references = {x.get("ReferenceNumber"): x for x in record.get("Reference", [])}
        result = []
        for node, path in sections(record):
            if node.get("TOCHeading") != heading:
                continue
            for number, info in enumerate(node.get("Information", [])):
                val = info.get("Value", {})
                strings = list(text_values(val))
                numeric = val.get("Number", [])
                if not isinstance(numeric, list):
                    numeric = [numeric]
                entries = [(x, val.get("Unit", "")) for x in numeric] + [(x, "") for x in strings]
                for entry_index, (entry, unit) in enumerate(entries):
                    property_id = PUBCHEM_PROPERTY_MAP[heading]
                    # PUG View 的 Unit 可能是 "mg/L (at 25 °C)"，必须拆出条件。
                    text = f"{entry} {unit}".strip()
                    value, unit, qualifier = parse_quantity(text, dimensionless=property_id in DIMENSIONLESS)
                    conditions = parse_conditions(text)
                    if property_id == "water_solubility" and conditions.get("solvent") not in {None, "water"}:
                        property_id = "solubility"
                    # 熔沸点的值本身不是独立的测量温度条件。
                    if property_id in {"melting_point", "boiling_point"}:
                        conditions.pop("temperature", None)
                    ref = references.get(info.get("ReferenceNumber"), {})
                    context = " ".join((text, str(info.get("Name", "")), str(info.get("Description", ""))))
                    evidence = PropertyEvidence(**evidence_base(identity, raw), property_id=property_id, value=value, unit=unit,
                        qualifier=qualifier, evidence_type=evidence_kind(context), method=str(info.get("Name", "")),
                        reference={"source": ref, "reference": info.get("Reference", []), "url": info.get("URL", raw.endpoint)},
                        extra={"heading": heading, "section_path": list(path), "information_index": number,
                               "entry_index": entry_index, "original_information": info}, **conditions)
                    result.append(normalize_evidence(evidence))
        return result

    def parse_hazard(self, raw, identity):
        record = raw.json().get("Record", {})
        if record.get("RecordNumber") and str(record["RecordNumber"]) != identity.identifiers["pubchem_cid"]:
            raise ValueError("GHS RecordNumber does not match observed CID")
        references = {x.get("ReferenceNumber"): x for x in record.get("Reference", [])}
        result = []
        for node, path in sections(record):
            for info in node.get("Information", []):
                texts = list(text_values(info))
                codes = sorted({code for item in texts for code in re.findall(r"\bH\d{3}\b", item)})
                if not codes:
                    continue
                result.append(PropertyEvidence(**evidence_base(identity, raw), property_id="ghs_classification", value={
                    "codes": codes, "statements": [x for x in texts if re.search(r"\bH\d{3}\b", x)],
                    "signal_words": sorted({word for x in texts for word in re.findall(r"\b(?:Danger|Warning)\b", x, re.I)}),
                    "annotation_text": texts}, evidence_type="summary", method="PubChem PUG View GHS Classification",
                    reference={"source": references.get(info.get("ReferenceNumber"), {}), "reference": info.get("Reference", [])},
                    extra={"condition_matching": False, "section_path": list(path), "information_index": len(result),
                           "original_information": info}))
        return result

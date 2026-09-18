import xml.etree.ElementTree as ET

from 核心系统.公开证据.数据结构 import PropertyEvidence, stable_hash
from 核心系统.公开证据.单位标准化 import convert, normalize_evidence
from .mapping import THERMOML_CONDITION_MAP, THERMOML_PROPERTY_MAP

PARSER_VERSION = "thermoml-1.0"


def xml_text(element):
    return ET.tostring(element, encoding="unicode") if element is not None else ""


def text(element, name):
    return element.findtext(".//" + name, default="")


def document_tree(body):
    if "<!DOCTYPE" in body.upper() or "<!ENTITY" in body.upper():
        raise ValueError("DTD/entity declarations are not supported")
    root = ET.fromstring(body)
    for node in root.iter():
        node.tag = node.tag.split("}")[-1]
    return root


class ThermoMLParser:
    def resolve_org_number(self, raw, identity):
        root = document_tree(raw.body)
        explicit = identity.identifiers.get("thermoml_org_num", "")
        hits = []
        for compound in root.findall("Compound"):
            number = text(compound, "nOrgNum")
            key = text(compound, "sStandardInChIKey")
            cas = text(compound, "sCASRegistryNumber")
            if (explicit and number == explicit) or (identity.inchikey and key == identity.inchikey) or (
                    identity.identifiers.get("cas") and cas == identity.identifiers["cas"]):
                if identity.inchikey and key and key != identity.inchikey:
                    raise ValueError("ThermoML compound conflicts with observed form")
                hits.append(number)
        if len(set(hits)) != 1:
            raise ValueError("ThermoML document has no unique matching observed compound")
        return hits[0]

    def _condition(self, definition, value, conditions, extras):
        labels = [(node.tag, node.text or "") for node in definition.iter() if node.text and node.text.strip()]
        mapped = next((THERMOML_CONDITION_MAP[label] for _, label in labels if label in THERMOML_CONDITION_MAP), None)
        if mapped:
            field, unit = mapped
            canonical_value, canonical_unit = convert(float(value), unit)
            conditions[field] = {"value": canonical_value, "unit": canonical_unit} if field == "wavelength" else canonical_value
        else:
            extras.append({"definition_xml": xml_text(definition), "value": value})

    def parse(self, raw, identity):
        root = document_tree(raw.body)
        citation = xml_text(root.find("Citation"))
        target_number = identity.identifiers["thermoml_org_num"]
        compounds = {text(c, "nOrgNum"): xml_text(c) for c in root.findall("Compound")}
        evidence = []
        for block_index, block in enumerate(root.findall("PureOrMixtureData")):
            components = [text(c, "nOrgNum") for c in block.findall("Component")]
            if target_number not in components:
                continue
            mixture = len(components) > 1
            compound_id = ("thermoml:mixture:" + stable_hash({"components": [compounds.get(c, c) for c in sorted(components)]})
                           if mixture else identity.compound_id)
            variables = {text(v, "nVarNumber"): v for v in block.findall("Variable")}
            properties = {text(p, "nPropNumber"): p for p in block.findall("Property")}
            for point_index, point in enumerate(block.findall("NumValues")):
                conditions, other_conditions = {}, []
                for constraint in block.findall("Constraint"):
                    self._condition(constraint, text(constraint, "nConstraintValue"), conditions, other_conditions)
                for var in point.findall("VariableValue"):
                    definition = variables.get(text(var, "nVarNumber"))
                    if definition is not None:
                        self._condition(definition, text(var, "nVarValue"), conditions, other_conditions)
                concentrations = [c for c in other_conditions if any(word in c["definition_xml"].lower()
                                  for word in ("fraction", "molality", "concentration", "composition"))]
                if concentrations:
                    conditions["concentration"] = concentrations
                for value in point.findall("PropertyValue"):
                    prop_number = text(value, "nPropNumber")
                    definition = properties.get(prop_number)
                    if definition is None:
                        raise ValueError("ThermoML property number has no definition")
                    name = text(definition, "ePropName") or text(definition, "sPropName")
                    property_id, unit = THERMOML_PROPERTY_MAP.get(name, ("thermoml:" + name, name.rsplit(", ", 1)[1] if ", " in name else ""))
                    prediction = definition.find(".//Prediction")
                    critical = definition.find(".//CriticalEvaluation")
                    kind = "predicted" if prediction is not None else "summary" if critical is not None else "measured"
                    method = text(definition, "eMethodName") or text(definition, "sMethodName")
                    prop_conditions = dict(conditions)
                    phase = text(definition, "ePropPhase")
                    if phase:
                        prop_conditions["phase"] = phase
                    # 标准、扩展、组合等不确定度类型完整保留，不能混成一个 ± 数字。
                    uncertainties = [xml_text(node) for node in value if "Uncert" in node.tag]
                    uncertainties.extend(xml_text(node) for node in definition if "Uncert" in node.tag)
                    evidence.append(normalize_evidence(PropertyEvidence(
                        compound_id=compound_id, chemical_form="mixture" if mixture else identity.chemical_form,
                        property_id=property_id, value=float(text(value, "nPropValue")), unit=unit, evidence_type=kind,
                        method=method, uncertainty={"xml": uncertainties} if uncertainties else None, source="thermoml",
                        source_record_id=f"{raw.endpoint}#dataset={text(block, 'nPureOrMixtureDataNumber') or block_index}:property={prop_number}:point={point_index}",
                        retrieved_at=raw.retrieved_at, parser_version=PARSER_VERSION, raw_record_id=raw.raw_record_id,
                        observed_structure="" if mixture else identity.observed_structure,
                        standardized_parent_structure="" if mixture else identity.standardized_parent_structure,
                        reference={"citation_xml": citation, "url": raw.endpoint},
                        extra={"property_definition_xml": xml_text(definition), "point_xml": xml_text(point),
                               "conditions": other_conditions, "components": [compounds.get(c, c) for c in components],
                               "dataset_metadata_xml": "".join(xml_text(node) for node in block if node.tag != "NumValues")},
                        **prop_conditions)))
        return evidence

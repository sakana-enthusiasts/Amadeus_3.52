from html.parser import HTMLParser
import re

from 核心系统.公开证据.数据结构 import PropertyEvidence
from 核心系统.公开证据.单位标准化 import normalize_evidence
from ..解析工具 import parse_quantity, parse_conditions
from .mapping import NIST_PROPERTY_MAP

PARSER_VERSION = "nist-webbook-1.0"


class TableParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.tables = []
        self.table = None
        self.row = None
        self.cell = None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "table" and "data" in attrs.get("class", "").split():
            self.table = {"label": attrs.get("aria-label", ""), "rows": []}
        elif self.table is not None and tag == "tr":
            self.row = {"class": attrs.get("class", ""), "cells": [], "links": []}
        elif self.row is not None and tag in {"td", "th"}:
            self.cell = []
        elif self.row is not None and tag == "a":
            self.row["links"].append(attrs.get("href", ""))

    def handle_data(self, data):
        if self.cell is not None:
            self.cell.append(data)

    def handle_endtag(self, tag):
        if tag in {"td", "th"} and self.cell is not None and self.row is not None:
            self.row["cells"].append("".join(self.cell).strip())
            self.cell = None
        elif tag == "tr" and self.row is not None:
            self.table["rows"].append(self.row)
            self.row = None
        elif tag == "table" and self.table is not None:
            self.tables.append(self.table)
            self.table = None


class WebBookParser:
    def parse(self, raw, identity):
        if "Chemical Not Found" in raw.body or "Search Results" in raw.body:
            return []
        match = re.search(r"InChIKey(?:</[^>]+>|\s|:)*([A-Z]{14}-[A-Z]{10}-[A-Z])", raw.body)
        if identity.inchikey and match and match.group(1) != identity.inchikey:
            raise ValueError("WebBook InChIKey conflicts with observed form")
        parser = TableParser()
        parser.feed(raw.body)
        evidence = []
        for table_index, table in enumerate(parser.tables):
            for row_index, row in enumerate(table["rows"]):
                cells = row["cells"]
                if len(cells) < 3:
                    continue
                quantity = cells[0].replace(" ", "").replace("\n", "")
                property_id = NIST_PROPERTY_MAP.get(quantity)
                if not property_id:
                    continue
                value, unit, qualifier = parse_quantity(cells[1], cells[2])
                method = cells[3] if len(cells) > 3 else ""
                conditions = parse_conditions(" ".join(cells[5:]))
                uncertainty = parse_conditions(cells[1]).get("uncertainty")
                if uncertainty is not None:
                    conditions["uncertainty"] = uncertainty
                kind = "measured" if "exp" in row["class"].split() else "summary"
                if method == "AVG" or "Average" in " ".join(cells):
                    kind = "summary"
                evidence.append(normalize_evidence(PropertyEvidence(
                    compound_id=identity.compound_id, chemical_form=identity.chemical_form, property_id=property_id,
                    value=value, unit=unit, qualifier=qualifier, evidence_type=kind, method=method, source="nist",
                    source_record_id=identity.identifiers["nist_id"], retrieved_at=raw.retrieved_at,
                    parser_version=PARSER_VERSION, raw_record_id=raw.raw_record_id,
                    observed_structure=identity.observed_structure, standardized_parent_structure=identity.standardized_parent_structure,
                    reference={"citation": cells[4] if len(cells) > 4 else "", "links": row["links"], "url": raw.endpoint},
                    extra={"table_index": table_index, "row_index": row_index, "table_label": table["label"], "original_row": row},
                    **conditions)))
        return evidence

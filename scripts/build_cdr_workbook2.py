from __future__ import annotations

import csv
import json
import math
import re
import unicodedata
import zipfile
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Iterable, Iterator
from xml.sax.saxutils import escape as xml_escape


ROOT = Path(__file__).resolve().parents[1]
WORKING_CSV = ROOT / "cleaned data" / "exports" / "2024 CDR Consumer and Commercial Use Information_clean_working_20260622_120407.csv"
OUTPUT_DIR = ROOT / "outputs" / f"cdr_workbook_{datetime.now():%Y%m%d_%H%M%S}"
XLSX_PATH = OUTPUT_DIR / "cdr_notebook_tables.xlsx"
MANIFEST_PATH = OUTPUT_DIR / "build_manifest.json"


def log(message: str) -> None:
    print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] {message}", flush=True)


def normalize_entity_text(value: str | None) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    text = unicodedata.normalize("NFKC", text).replace("\u00a0", " ")
    text = " ".join(text.split())
    return text or None


def sanitize_xml_text(value: str) -> str:
    value = re.sub(r"[\x00-\x08\x0B\x0C\x0E-\x1F]", "", value)
    return xml_escape(value)


def is_blank(value: str | None) -> bool:
    return value is None or str(value).strip() == ""


def parse_number(value: str | None):
    if is_blank(value):
        return None
    text = str(value).strip().replace(",", "")
    if re.fullmatch(r"[-+]?\d+", text):
        return int(text)
    try:
        return float(text)
    except Exception:
        return None


def col_name(index_1_based: int) -> str:
    result = ""
    value = index_1_based
    while value:
        value, remainder = divmod(value - 1, 26)
        result = chr(65 + remainder) + result
    return result


def read_rows(path: Path) -> Iterator[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            yield row


def read_headers(path: Path) -> list[str]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.reader(handle)
        return next(reader)


def cell_xml(ref: str, value, header: bool = False) -> str:
    if value is None or value == "":
        return ""
    style = ' s="1"' if header else ""
    if isinstance(value, bool):
        return f'<c r="{ref}" t="b"{style}><v>{1 if value else 0}</v></c>'
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
            return ""
        return f'<c r="{ref}"{style}><v>{value}</v></c>'
    text = sanitize_xml_text(str(value))
    return f'<c r="{ref}" t="inlineStr"{style}><is><t xml:space="preserve">{text}</t></is></c>'


def last_column_ref(headers: list[str]) -> str:
    return col_name(len(headers))


def write_sheet_xml(zf: zipfile.ZipFile, part_name: str, headers: list[str], rows: Iterable[list]) -> int:
    row_count = 1
    last_col = last_column_ref(headers)
    with zf.open(part_name, "w") as handle:
        def write(text: str) -> None:
            handle.write(text.encode("utf-8"))

        write('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>')
        write(
            '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
            'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        )
        write(
            '<sheetViews><sheetView workbookViewId="0">'
            '<pane ySplit="1" topLeftCell="A2" activePane="bottomLeft" state="frozen"/>'
            '<selection pane="bottomLeft" activeCell="A1" sqref="A1"/>'
            '</sheetView></sheetViews>'
        )
        write("<sheetFormatPr defaultRowHeight=\"15\"/>")
        write("<sheetData>")
        write("<row r=\"1\">")
        for idx, header in enumerate(headers, start=1):
            write(cell_xml(f"{col_name(idx)}1", header, header=True))
        write("</row>")
        for excel_row, row in enumerate(rows, start=2):
            write(f'<row r="{excel_row}">')
            for idx, value in enumerate(row, start=1):
                fragment = cell_xml(f"{col_name(idx)}{excel_row}", value)
                if fragment:
                    write(fragment)
            write("</row>")
            row_count += 1
        write("</sheetData>")
        write(f'<autoFilter ref="A1:{last_col}{row_count}"/>')
        write("</worksheet>")
    return row_count - 1


def normalize_working_row(row: dict[str, str], source_row_id: int) -> dict[str, str]:
    normalized = dict(row)
    normalized["source_row_id"] = source_row_id
    for column in [
        "standardized_parent_company_name",
        "foreign_parent_company_name",
        "domestic_parent_company_name",
        "chemical_id",
        "chemical_id_w_o_dashes",
        "chemical_id_type",
    ]:
        if column in row:
            normalized[f"{column}_normalized"] = normalize_entity_text(row.get(column))
    normalized["chemical_name_normalized"] = normalize_entity_text(row.get("chemical_name"))
    return normalized


def build_entity_table(entity_type: str, name_column: str, id_columns: list[str]) -> tuple[list[str], list[list]]:
    headers = ["entity_type", "canonical_entity_key", "canonical_entity_name", "source_columns", *id_columns]
    seen: set[tuple[str, str]] = set()
    rows: list[list] = []
    for row in read_rows(WORKING_CSV):
        name_value = normalize_entity_text(row.get(name_column))
        if not name_value:
            continue
        normalized_ids = [normalize_entity_text(row.get(column)) for column in id_columns]
        normalized_ids = [value for value in normalized_ids if value]
        key_value = normalized_ids[0] if normalized_ids else name_value
        pair = (key_value, name_value)
        if pair in seen:
            continue
        seen.add(pair)
        output = [entity_type, key_value, name_value, ", ".join([name_column, *id_columns])]
        for column in id_columns:
            output.append(normalize_entity_text(row.get(column)) or "")
        rows.append(output)
    rows.sort(key=lambda item: (item[2] or "", item[1] or ""))
    return headers, rows


def build_ontology_entities() -> tuple[list[str], list[list], dict[str, int]]:
    chem_headers, chem_rows = build_entity_table(
        "chemical",
        "chemical_name",
        ["chemical_id", "chemical_id_w_o_dashes", "chemical_id_type"],
    )
    company_headers, company_rows = build_entity_table(
        "company",
        "standardized_parent_company_name",
        [
            "foreign_parent_company_name",
            "domestic_parent_company_name",
            "foreign_pc_dun_bradstreet_number",
            "domestic_pc_dun_bradstreet_number",
        ],
    )
    headers = [
        "entity_type",
        "canonical_entity_key",
        "canonical_entity_name",
        "source_columns",
        "chemical_id",
        "chemical_id_w_o_dashes",
        "chemical_id_type",
        "foreign_parent_company_name",
        "domestic_parent_company_name",
        "foreign_pc_dun_bradstreet_number",
        "domestic_pc_dun_bradstreet_number",
    ]
    rows: list[list] = []
    for row in chem_rows:
        rows.append(row[:4] + [row[4], row[5], row[6], "", "", "", ""])
    for row in company_rows:
        rows.append(row[:4] + ["", "", "", row[4], row[5], row[6], row[7]])
    rows.sort(key=lambda item: (item[2] or "", item[1] or ""))
    counts = Counter(row[0] for row in rows)
    return headers, rows, dict(counts)


def build_company_table() -> tuple[list[str], list[list]]:
    headers = [
        "source_row_id",
        "company_name_source",
        "company_key",
        "foreign_parent_company_name",
        "foreign_parent_company_name_normalized",
        "domestic_parent_company_name",
        "domestic_parent_company_name_normalized",
        "foreign_pc_dun_bradstreet_number",
        "domestic_pc_dun_bradstreet_number",
    ]
    by_key: dict[str, list] = {}
    for source_row_id, row in enumerate(read_rows(WORKING_CSV)):
        normalized = normalize_working_row(row, source_row_id)
        key_value = normalized.get("standardized_parent_company_name_normalized")
        if is_blank(key_value) or key_value in by_key:
            continue
        by_key[key_value] = [
            source_row_id,
            row.get("standardized_parent_company_name", ""),
            key_value,
            row.get("foreign_parent_company_name", ""),
            normalized.get("foreign_parent_company_name_normalized", ""),
            row.get("domestic_parent_company_name", ""),
            normalized.get("domestic_parent_company_name_normalized", ""),
            row.get("foreign_pc_dun_bradstreet_number", ""),
            row.get("domestic_pc_dun_bradstreet_number", ""),
        ]
    return headers, list(by_key.values())


def build_chemical_table() -> tuple[list[str], list[list]]:
    headers = [
        "source_row_id",
        "chemical_name_source",
        "chemical_name_key",
        "chemical_id_source",
        "chemical_id_key",
        "chemical_id_without_dashes_source",
        "chemical_cas_key",
        "chemical_id_type_source",
        "chemical_id_type_key",
    ]
    by_key: dict[str, list] = {}
    for source_row_id, row in enumerate(read_rows(WORKING_CSV)):
        normalized = normalize_working_row(row, source_row_id)
        key_value = normalized.get("chemical_id_w_o_dashes_normalized")
        if is_blank(key_value) or key_value in by_key:
            continue
        by_key[key_value] = [
            source_row_id,
            row.get("chemical_name", ""),
            normalized.get("chemical_name_normalized", ""),
            row.get("chemical_id", ""),
            normalized.get("chemical_id_normalized", ""),
            row.get("chemical_id_w_o_dashes", ""),
            key_value,
            row.get("chemical_id_type", ""),
            normalized.get("chemical_id_type_normalized", ""),
        ]
    return headers, list(by_key.values())


def build_activity_fact() -> tuple[list[str], Iterator[list]]:
    headers = [
        "source_row_id",
        "company_key",
        "chemical_cas_key",
        "chemical_name_key",
        "activity",
        "cons_and_or_comm_use",
        "used_in_prod_for_children",
        "pct_byp_code",
        "percent_byproduct",
        "workers_code",
        "workers_reasonably_likely_exposed",
        "max_conc_code",
        "maximum_concentration",
        "c_c_prod_cat_code",
        "consumer_commercial_product_category",
        "c_c_fc_code",
        "consumer_commercial_function_category",
        "joint_fc_code",
        "joint_function_category",
    ]

    def rows() -> Iterator[list]:
        for source_row_id, row in enumerate(read_rows(WORKING_CSV)):
            normalized = normalize_working_row(row, source_row_id)
            yield [
                source_row_id,
                normalized.get("standardized_parent_company_name_normalized", ""),
                normalized.get("chemical_id_w_o_dashes_normalized", ""),
                normalized.get("chemical_name_normalized", ""),
                row.get("activity", ""),
                row.get("cons_and_or_comm_use", ""),
                row.get("used_in_prod_for_children", ""),
                row.get("pct_byp_code", ""),
                row.get("percent_byproduct", ""),
                row.get("workers_code", ""),
                row.get("workers_reasonably_likely_exposed", ""),
                row.get("max_conc_code", ""),
                row.get("maximum_concentration", ""),
                row.get("c_c_prod_cat_code", ""),
                row.get("consumer_commercial_product_category", ""),
                row.get("c_c_fc_code", ""),
                row.get("consumer_commercial_function_category", ""),
                row.get("joint_fc_code", ""),
                row.get("joint_function_category", ""),
            ]

    return headers, rows()


def build_quantity_fact() -> tuple[list[str], Iterator[list]]:
    quantity_columns = [
        "2023_domestic_pv",
        "2023_import_pv",
        "2023_pv",
        "2022_pv",
        "2021_pv",
        "2020_pv",
        "2023_v_used_on_site",
        "2023_v_exported",
        "2023_nationally_aggregated_pv",
        "2022_nationally_aggregated_pv",
        "2021_nationally_aggregated_pv",
        "2020_nationally_aggregated_pv",
        "c_c_pv_pct",
    ]
    headers = [
        "source_row_id",
        "company_key",
        "chemical_cas_key",
        "chemical_name_key",
        "quantity_type",
        "quantity_value",
        "quantity_value_numeric",
    ]

    def rows() -> Iterator[list]:
        for source_row_id, row in enumerate(read_rows(WORKING_CSV)):
            normalized = normalize_working_row(row, source_row_id)
            for quantity_column in quantity_columns:
                value = row.get(quantity_column, "")
                if is_blank(value):
                    continue
                yield [
                    source_row_id,
                    normalized.get("standardized_parent_company_name_normalized", ""),
                    normalized.get("chemical_id_w_o_dashes_normalized", ""),
                    normalized.get("chemical_name_normalized", ""),
                    quantity_column,
                    value,
                    parse_number(value),
                ]

    return headers, rows()


def build_physical_form_fact() -> tuple[list[str], Iterator[list]]:
    headers = ["source_row_id", "chemical_name_key", "chemical_cas_key", "physical_form"]

    def rows() -> Iterator[list]:
        for source_row_id, row in enumerate(read_rows(WORKING_CSV)):
            forms: list[str] = []
            raw_forms = row.get("physical_form_s_list", "")
            if not is_blank(raw_forms):
                forms = [normalize_entity_text(part) for part in str(raw_forms).split(";")]
                forms = [value for value in forms if value]
            if not forms:
                flag_columns = [column for column in row.keys() if column.startswith("pf_ppv")]
                forms = [column for column in flag_columns if not is_blank(row.get(column))]
            if not forms:
                continue
            normalized = normalize_working_row(row, source_row_id)
            for form in forms:
                yield [
                    source_row_id,
                    normalized.get("chemical_name_normalized", ""),
                    normalized.get("chemical_id_w_o_dashes_normalized", ""),
                    form,
                ]

    return headers, rows()


def build_checklist(has_physical_form_fact: bool) -> tuple[list[str], list[list]]:
    headers = ["check", "status", "details"]
    available_columns = set(read_headers(WORKING_CSV))
    rows = [
        [
            "Encoding artifacts",
            "needs_review" if any(name.startswith("pf_ppv") for name in available_columns) else "ok",
            "Inspect any remaining mojibake in headers or range labels.",
        ],
        [
            "Company key",
            "ok" if "standardized_parent_company_name" in available_columns else "needs_review",
            "Use normalized parent company names as the primary company index key.",
        ],
        [
            "Chemical key",
            "ok" if "chemical_id_w_o_dashes" in available_columns else "needs_review",
            "Use a normalized chemical ID without dashes as the primary chemical key.",
        ],
    ]
    for code_column, label_column in [
        ("pct_byp_code", "percent_byproduct"),
        ("workers_code", "workers_reasonably_likely_exposed"),
        ("max_conc_code", "maximum_concentration"),
        ("c_c_prod_cat_code", "consumer_commercial_product_category"),
        ("c_c_fc_code", "consumer_commercial_function_category"),
        ("joint_fc_code", "joint_function_category"),
    ]:
        rows.append(
            [
                f"{code_column} / {label_column}",
                "ok" if code_column in available_columns and label_column in available_columns else "needs_review",
                "Keep code and label columns together until lookup validation is complete.",
            ]
        )

    sentinel_counts = {"CBI": 0, "NKRA": 0}
    for row in read_rows(WORKING_CSV):
        for value in row.values():
            if value is None:
                continue
            text = str(value)
            for term in sentinel_counts:
                if term in text:
                    sentinel_counts[term] += 1
    for term, hits in sentinel_counts.items():
        rows.append(
            [
                f"Sentinel {term}",
                "needs_review" if hits else "ok",
                f"Found {hits:,} occurrences; confirm whether the term means confidential, unknown, or not applicable.",
            ]
        )

    rows.append(
        [
            "Source row provenance",
            "ok" if "source_row_id" in available_columns else "needs_review",
            "Every derived table should keep source_row_id for traceability.",
        ]
    )
    rows.append(
        [
            "Atomic physical forms",
            "ok" if has_physical_form_fact else "needs_review",
            "Physical-form lists should be split into atomic rows before table creation.",
        ]
    )
    return headers, rows


def build_entity_counts(ontology_rows: list[list]) -> tuple[list[str], list[list]]:
    headers = ["entity_type", "entity_count"]
    counts = Counter(row[0] for row in ontology_rows)
    rows = [[entity_type, count] for entity_type, count in sorted(counts.items())]
    return headers, rows


def build_session_log(counts: dict[str, int]) -> tuple[list[str], list[list]]:
    headers = ["session_log"]
    rows = [
        ["Loaded cleaned source CSV."],
        [f"Ontology seed rows: {counts['ontology_entities']:,}."],
        [f"Company table rows: {counts['company_table']:,}."],
        [f"Chemical table rows: {counts['chemical_table']:,}."],
        [f"Company activity fact rows: {counts['company_activity_fact']:,}."],
        [f"Quantity fact rows: {counts['quantity_fact']:,}."],
        [f"Physical-form fact rows: {counts['physical_form_fact']:,}."],
        ["Workbook generated from notebook-derived tables."],
    ]
    return headers, rows


def write_sheet_package(zf: zipfile.ZipFile, part_name: str, headers: list[str], rows: Iterable[list]) -> int:
    log(f"Writing {part_name} ...")
    count = write_sheet_xml(zf, part_name, headers, rows)
    log(f"Finished {part_name} with {count:,} data rows.")
    return count


def write_metadata(path: Path, sheet_specs: list[dict]) -> None:
    workbook_sheets = []
    rels = []
    overrides = []
    for idx, spec in enumerate(sheet_specs, start=1):
        workbook_sheets.append(f'<sheet name="{sanitize_xml_text(spec["name"])}" sheetId="{idx}" r:id="rId{idx}"/>')
        rels.append(
            f'<Relationship Id="rId{idx}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="{spec["part_name"].replace("xl/", "")}"/>'
        )
        overrides.append(
            f'<Override PartName="/{spec["part_name"]}" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
        )

    workbook_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        "<sheets>"
        + "".join(workbook_sheets)
        + "</sheets></workbook>"
    )
    workbook_rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        + "".join(rels)
        + '<Relationship Id="rId99" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>'
        "</Relationships>"
    )
    styles_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        "<fonts count=\"2\">"
        "<font><sz val=\"11\"/><color theme=\"1\"/><name val=\"Calibri\"/><family val=\"2\"/></font>"
        "<font><b/><color rgb=\"FFFFFFFF\"/><sz val=\"11\"/><name val=\"Calibri\"/><family val=\"2\"/></font>"
        "</fonts>"
        "<fills count=\"3\">"
        "<fill><patternFill patternType=\"none\"/></fill>"
        "<fill><patternFill patternType=\"gray125\"/></fill>"
        "<fill><patternFill patternType=\"solid\"><fgColor rgb=\"FF1F4E78\"/><bgColor indexed=\"64\"/></patternFill></fill>"
        "</fills>"
        "<borders count=\"1\"><border><left/><right/><top/><bottom/><diagonal/></border></borders>"
        "<cellStyleXfs count=\"1\"><xf numFmtId=\"0\" fontId=\"0\" fillId=\"0\" borderId=\"0\"/></cellStyleXfs>"
        "<cellXfs count=\"2\">"
        "<xf numFmtId=\"0\" fontId=\"0\" fillId=\"0\" borderId=\"0\" xfId=\"0\"/>"
        "<xf numFmtId=\"0\" fontId=\"1\" fillId=\"2\" borderId=\"0\" xfId=\"0\" applyFont=\"1\" applyFill=\"1\"/>"
        "</cellXfs>"
        "<cellStyles count=\"1\"><cellStyle name=\"Normal\" xfId=\"0\" builtinId=\"0\"/></cellStyles>"
        "</styleSheet>"
    )
    content_types = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
        '<Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>'
        + "".join(overrides)
        + "</Types>"
    )
    root_rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>'
        "</Relationships>"
    )
    timestamp = datetime.utcnow().isoformat(timespec="seconds") + "Z"
    core_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" '
        'xmlns:dc="http://purl.org/dc/elements/1.1/" '
        'xmlns:dcterms="http://purl.org/dc/terms/" '
        'xmlns:dcmitype="http://purl.org/dc/dcmitype/" '
        'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">'
        "<dc:title>CDR Notebook Tables</dc:title>"
        "<dc:creator>Codex</dc:creator>"
        "<cp:lastModifiedBy>Codex</cp:lastModifiedBy>"
        f'<dcterms:created xsi:type="dcterms:W3CDTF">{timestamp}</dcterms:created>'
        f'<dcterms:modified xsi:type="dcterms:W3CDTF">{timestamp}</dcterms:modified>'
        "</cp:coreProperties>"
    )
    app_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties" '
        'xmlns:vt="http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes">'
        "<Application>Microsoft Excel</Application>"
        "</Properties>"
    )
    with zipfile.ZipFile(path, "a", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        zf.writestr("[Content_Types].xml", content_types)
        zf.writestr("_rels/.rels", root_rels)
        zf.writestr("xl/workbook.xml", workbook_xml)
        zf.writestr("xl/_rels/workbook.xml.rels", workbook_rels)
        zf.writestr("xl/styles.xml", styles_xml)
        zf.writestr("docProps/core.xml", core_xml)
        zf.writestr("docProps/app.xml", app_xml)


def main() -> None:
    log(f"Source CSV: {WORKING_CSV}")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    ontology_headers, ontology_rows, ontology_counts = build_ontology_entities()
    entity_count_headers, entity_count_rows = build_entity_counts(ontology_rows)
    company_headers, company_rows = build_company_table()
    chemical_headers, chemical_rows = build_chemical_table()
    activity_headers, activity_rows = build_activity_fact()
    quantity_headers, quantity_rows = build_quantity_fact()
    physical_headers, physical_rows = build_physical_form_fact()
    checklist_headers, checklist_rows = build_checklist(has_physical_form_fact=True)

    counts: dict[str, int] = {}

    non_index_specs = [
        {"key": "ontology_entities", "name": "Entity Ontology Seed", "part_name": "xl/worksheets/sheet2.xml", "headers": ontology_headers, "rows": ontology_rows},
        {"key": "entity_counts", "name": "Entity Counts", "part_name": "xl/worksheets/sheet3.xml", "headers": entity_count_headers, "rows": entity_count_rows},
        {"key": "checklist", "name": "Checklist", "part_name": "xl/worksheets/sheet4.xml", "headers": checklist_headers, "rows": checklist_rows},
        {"key": "company_table", "name": "Company Table", "part_name": "xl/worksheets/sheet5.xml", "headers": company_headers, "rows": company_rows},
        {"key": "chemical_table", "name": "Chemical Table", "part_name": "xl/worksheets/sheet6.xml", "headers": chemical_headers, "rows": chemical_rows},
        {"key": "company_activity_fact", "name": "Company Activity Fact", "part_name": "xl/worksheets/sheet7.xml", "headers": activity_headers, "rows": activity_rows},
        {"key": "quantity_fact", "name": "Quantity Fact", "part_name": "xl/worksheets/sheet8.xml", "headers": quantity_headers, "rows": quantity_rows},
        {"key": "physical_form_fact", "name": "Physical Form Fact", "part_name": "xl/worksheets/sheet9.xml", "headers": physical_headers, "rows": physical_rows},
    ]

    with zipfile.ZipFile(XLSX_PATH, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        for spec in non_index_specs:
            counts[spec["key"]] = write_sheet_package(zf, spec["part_name"], spec["headers"], spec["rows"])

        session_headers, session_rows = build_session_log({
            "ontology_entities": len(ontology_rows),
            "company_table": counts["company_table"],
            "chemical_table": counts["chemical_table"],
            "company_activity_fact": counts["company_activity_fact"],
            "quantity_fact": counts["quantity_fact"],
            "physical_form_fact": counts["physical_form_fact"],
        })
        counts["session_log"] = len(session_rows)

        index_headers = ["sheet_name", "purpose", "rows"]
        index_rows = [
            ["Entity Ontology Seed", "Combined company and chemical entity seed list", counts["ontology_entities"]],
            ["Entity Counts", "Count of ontology entities by type", counts["entity_counts"]],
            ["Checklist", "Normalization and table readiness checklist", counts["checklist"]],
            ["Company Table", "Canonical company dimension table", counts["company_table"]],
            ["Chemical Table", "Canonical chemical dimension table", counts["chemical_table"]],
            ["Company Activity Fact", "Company/chemical activity fact table", counts["company_activity_fact"]],
            ["Quantity Fact", "Long-form quantity table", counts["quantity_fact"]],
            ["Physical Form Fact", "Atomic physical-form rows", counts["physical_form_fact"]],
            ["Session Log", "Build notes and status", counts["session_log"]],
        ]
        counts["index"] = len(index_rows)
        write_sheet_package(zf, "xl/worksheets/sheet1.xml", index_headers, index_rows)
        write_sheet_package(zf, "xl/worksheets/sheet10.xml", session_headers, session_rows)

    all_specs = [
        {"name": "Index", "part_name": "xl/worksheets/sheet1.xml"},
        {"name": "Entity Ontology Seed", "part_name": "xl/worksheets/sheet2.xml"},
        {"name": "Entity Counts", "part_name": "xl/worksheets/sheet3.xml"},
        {"name": "Checklist", "part_name": "xl/worksheets/sheet4.xml"},
        {"name": "Company Table", "part_name": "xl/worksheets/sheet5.xml"},
        {"name": "Chemical Table", "part_name": "xl/worksheets/sheet6.xml"},
        {"name": "Company Activity Fact", "part_name": "xl/worksheets/sheet7.xml"},
        {"name": "Quantity Fact", "part_name": "xl/worksheets/sheet8.xml"},
        {"name": "Physical Form Fact", "part_name": "xl/worksheets/sheet9.xml"},
        {"name": "Session Log", "part_name": "xl/worksheets/sheet10.xml"},
    ]
    write_metadata(XLSX_PATH, all_specs)

    MANIFEST_PATH.write_text(
        json.dumps(
            {
                "source_csv": str(WORKING_CSV),
                "output_xlsx": str(XLSX_PATH),
                "counts": counts,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    log(f"Workbook written to {XLSX_PATH}")
    log(f"Manifest written to {MANIFEST_PATH}")


if __name__ == "__main__":
    main()

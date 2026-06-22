from __future__ import annotations

import csv
import json
import math
import re
import unicodedata
import zipfile
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Callable, Iterable, Iterator
from xml.sax.saxutils import escape as xml_escape


ROOT = Path(__file__).resolve().parents[1]
WORKING_CSV = ROOT / "cleaned data" / "exports" / "2024 CDR Consumer and Commercial Use Information_clean_working_20260622_120407.csv"
RAW_CSV = ROOT / "cleaned data" / "2024 CDR Consumer and Commercial Use Information_clean.csv"
OUTPUT_DIR = ROOT / "outputs" / f"cdr_workbook_{datetime.now():%Y%m%d_%H%M%S}"
XLSX_PATH = OUTPUT_DIR / "cdr_notebook_tables.xlsx"
MANIFEST_PATH = OUTPUT_DIR / "build_manifest.json"


def log(message: str) -> None:
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{stamp}] {message}", flush=True)


def sanitize_xml_text(value: str) -> str:
    value = re.sub(r"[\x00-\x08\x0B\x0C\x0E-\x1F]", "", value)
    return xml_escape(value)


def normalize_entity_text(value: str | None) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    text = unicodedata.normalize("NFKC", text)
    text = text.replace("\u00a0", " ")
    text = " ".join(text.split())
    return text or None


def standardize_column_name(name: str) -> str:
    text = unicodedata.normalize("NFKC", name).strip().lower()
    text = text.replace("&", "and")
    text = re.sub(r"[^0-9a-z]+", "_", text)
    text = re.sub(r"_+", "_", text).strip("_")
    return text


def col_name(index_1_based: int) -> str:
    result = ""
    value = index_1_based
    while value:
        value, remainder = divmod(value - 1, 26)
        result = chr(65 + remainder) + result
    return result


def is_blank(value: str | None) -> bool:
    return value is None or str(value).strip() == ""


def parse_number(value: str | None):
    if is_blank(value):
        return None
    text = str(value).strip().replace(",", "")
    try:
        if re.fullmatch(r"[-+]?\d+", text):
            return int(text)
        return float(text)
    except Exception:
        return None


def read_csv_rows(path: Path) -> Iterator[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            yield row


def read_csv_header(path: Path) -> list[str]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.reader(handle)
        return next(reader)


def write_xlsx_cell(ref: str, value, header: bool = False) -> str:
    if value is None or value == "":
        return ""
    style = ' s="1"' if header else ""
    if isinstance(value, bool):
        return f'<c r="{ref}" t="b"{style}><v>{1 if value else 0}</v></c>'
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if isinstance(value, float):
            if math.isnan(value) or math.isinf(value):
                return f'<c r="{ref}" t="inlineStr"{style}><is><t /></is></c>'
            text = format(value, "g")
        else:
            text = str(value)
        return f'<c r="{ref}"{style}><v>{text}</v></c>'
    text = sanitize_xml_text(str(value))
    return f'<c r="{ref}" t="inlineStr"{style}><is><t xml:space="preserve">{text}</t></is></c>'


def write_worksheet_xml(
    zip_handle: zipfile.ZipFile,
    part_name: str,
    sheet_title: str,
    headers: list[str],
    rows: Iterable[list],
) -> int:
    last_col = col_name(len(headers))
    row_count = 0
    with zip_handle.open(part_name, "w") as file_handle:
        write = lambda text: file_handle.write(text.encode("utf-8"))
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
        write(f'<dimension ref="A1:{last_col}1"/>')
        write("<sheetFormatPr defaultRowHeight=\"15\"/>")
        write("<sheetData>")
        write("<row r=\"1\">")
        for col_idx, header in enumerate(headers, start=1):
            ref = f"{col_name(col_idx)}1"
            write(write_xlsx_cell(ref, header, header=True))
        write("</row>")
        row_count = 1
        for excel_row_idx, row in enumerate(rows, start=2):
            write(f'<row r="{excel_row_idx}">')
            for col_idx, value in enumerate(row, start=1):
                cell = write_xlsx_cell(f"{col_name(col_idx)}{excel_row_idx}", value)
                if cell:
                    write(cell)
            write("</row>")
            row_count += 1
        write("</sheetData>")
        write(f'<autoFilter ref="A1:{last_col}{row_count}"/>')
        write("</worksheet>")
    return row_count - 1


def source_row_with_normalized_fields(row: dict[str, str], source_row_id: int) -> dict[str, str]:
    normalized = dict(row)
    normalized["source_row_id"] = source_row_id
    for column in [
        "standardized_parent_company_name",
        "foreign_parent_company_name",
        "domestic_parent_company_name",
    ]:
        if column in row:
            normalized[f"{column}_normalized"] = normalize_entity_text(row.get(column))
    for column in ["chemical_id", "chemical_id_w_o_dashes", "chemical_id_type"]:
        if column in row:
            normalized[f"{column}_normalized"] = normalize_entity_text(row.get(column))
    normalized["chemical_name_normalized"] = normalize_entity_text(row.get("chemical_name"))
    return normalized


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
    for source_row_id, row in enumerate(read_csv_rows(WORKING_CSV)):
        normalized = source_row_with_normalized_fields(row, source_row_id)
        company_key = normalized.get("standardized_parent_company_name_normalized")
        if is_blank(company_key):
            continue
        if company_key in by_key:
            continue
        by_key[company_key] = [
            source_row_id,
            row.get("standardized_parent_company_name", ""),
            company_key,
            row.get("foreign_parent_company_name", ""),
            normalized.get("foreign_parent_company_name_normalized", ""),
            row.get("domestic_parent_company_name", ""),
            normalized.get("domestic_parent_company_name_normalized", ""),
            row.get("foreign_pc_dun_bradstreet_number", ""),
            row.get("domestic_pc_dun_bradstreet_number", ""),
        ]
    rows = list(by_key.values())
    return headers, rows


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
    for source_row_id, row in enumerate(read_csv_rows(WORKING_CSV)):
        normalized = source_row_with_normalized_fields(row, source_row_id)
        chemical_key = normalized.get("chemical_id_w_o_dashes_normalized")
        if is_blank(chemical_key):
            continue
        if chemical_key in by_key:
            continue
        by_key[chemical_key] = [
            source_row_id,
            row.get("chemical_name", ""),
            normalized.get("chemical_name_normalized", ""),
            row.get("chemical_id", ""),
            normalized.get("chemical_id_normalized", ""),
            row.get("chemical_id_w_o_dashes", ""),
            chemical_key,
            row.get("chemical_id_type", ""),
            normalized.get("chemical_id_type_normalized", ""),
        ]
    rows = list(by_key.values())
    return headers, rows


def build_entity_list(entity_type: str, name_column: str, id_columns: list[str]) -> list[list]:
    headers = [
        "entity_type",
        "canonical_entity_key",
        "canonical_entity_name",
        "source_columns",
        *id_columns,
    ]
    seen: set[tuple[str, str]] = set()
    rows: list[list] = []
    for row in read_csv_rows(WORKING_CSV):
        name_value = normalize_entity_text(row.get(name_column))
        if not name_value:
            continue
        available_ids = [normalize_entity_text(row.get(column)) for column in id_columns if column in row]
        available_ids = [value for value in available_ids if value]
        if available_ids:
            key_value = available_ids[0]
        else:
            key_value = name_value
        key_value = key_value or name_value
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
    chemical_headers, chemical_rows = build_entity_list(
        "chemical",
        "chemical_name",
        ["chemical_id", "chemical_id_w_o_dashes", "chemical_id_type"],
    )
    company_headers, company_rows = build_entity_list(
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
    for row in chemical_rows:
        rows.append(row[:4] + [row[4], row[5], row[6], "", "", "", ""])
    for row in company_rows:
        rows.append(row[:4] + ["", "", "", row[4], row[5], row[6], row[7]])
    rows.sort(key=lambda item: (item[2] or "", item[1] or ""))
    counts = Counter(item[0] for item in rows)
    return headers, rows, dict(counts)


def build_checklist(has_physical_form_fact: bool) -> tuple[list[str], list[list]]:
    headers = ["check", "status", "details"]
    available_columns = set(read_csv_header(WORKING_CSV))

    rows = []
    rows.append(
        [
            "Encoding artifacts",
            "needs_review" if any(name.startswith("pf_ppv") for name in available_columns) else "ok",
            "Inspect any remaining mojibake in headers or range labels.",
        ]
    )
    rows.append(
        [
            "Company key",
            "ok" if "standardized_parent_company_name" in available_columns else "needs_review",
            "Use normalized parent company names as the primary company index key.",
        ]
    )
    rows.append(
        [
            "Chemical key",
            "ok" if "chemical_id_w_o_dashes" in available_columns else "needs_review",
            "Use a normalized chemical ID without dashes as the primary chemical key.",
        ]
    )
    for code_column, label_column in [
        ("pct_byp_code", "percent_byproduct"),
        ("workers_code", "workers_reasonably_likely_exposed"),
        ("max_conc_code", "maximum_concentration"),
        ("c_c_prod_cat_code", "consumer_commercial_product_category"),
        ("c_c_fc_code", "consumer_commercial_function_category"),
        ("joint_fc_code", "joint_function_category"),
    ]:
        pair_status = "ok" if code_column in available_columns and label_column in available_columns else "needs_review"
        rows.append(
            [
                f"{code_column} / {label_column}",
                pair_status,
                "Keep code and label columns together until lookup validation is complete.",
            ]
        )

    sentinel_counts = {"CBI": 0, "NKRA": 0}
    for row in read_csv_rows(WORKING_CSV):
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


def build_company_activity_fact() -> tuple[list[str], Iterator[list]]:
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

    def row_iter() -> Iterator[list]:
        for source_row_id, row in enumerate(read_csv_rows(WORKING_CSV)):
            normalized = source_row_with_normalized_fields(row, source_row_id)
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

    return headers, row_iter()


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

    def row_iter() -> Iterator[list]:
        for source_row_id, row in enumerate(read_csv_rows(WORKING_CSV)):
            normalized = source_row_with_normalized_fields(row, source_row_id)
            for quantity_column in quantity_columns:
                raw_value = row.get(quantity_column, "")
                if is_blank(raw_value):
                    continue
                yield [
                    source_row_id,
                    normalized.get("standardized_parent_company_name_normalized", ""),
                    normalized.get("chemical_id_w_o_dashes_normalized", ""),
                    normalized.get("chemical_name_normalized", ""),
                    quantity_column,
                    raw_value,
                    parse_number(raw_value),
                ]

    return headers, row_iter()


def build_physical_form_fact() -> tuple[list[str], Iterator[list]]:
    headers = ["source_row_id", "chemical_name_key", "chemical_cas_key", "physical_form"]

    def row_iter() -> Iterator[list]:
        for source_row_id, row in enumerate(read_csv_rows(WORKING_CSV)):
            raw_forms = row.get("physical_form_s_list", "")
            forms: list[str] = []
            if not is_blank(raw_forms):
                forms = [normalize_entity_text(part) for part in str(raw_forms).split(";")]
                forms = [form for form in forms if form]
            if not forms:
                flag_columns = [column for column in row.keys() if column.startswith("pf_ppv")]
                forms = [column for column in flag_columns if not is_blank(row.get(column))]
            if not forms:
                continue
            normalized = source_row_with_normalized_fields(row, source_row_id)
            for form in forms:
                yield [
                    source_row_id,
                    normalized.get("chemical_name_normalized", ""),
                    normalized.get("chemical_id_w_o_dashes_normalized", ""),
                    form,
                ]

    return headers, row_iter()


def build_session_log(row_counts: dict[str, int]) -> tuple[list[str], list[list]]:
    headers = ["session_log"]
    rows = [
        ["Loaded source CSV and derived notebook-style tables."],
        [f"Source rows processed: {row_counts.get('company_table', 0):,} company keys observed."],
        [f"Chemical entities: {row_counts.get('chemical_table', 0):,} unique rows."],
        [f"Ontology entities: {row_counts.get('ontology_entities', 0):,} rows."],
        [f"Company activity fact rows: {row_counts.get('company_activity_fact', 0):,}."],
        [f"Quantity fact rows: {row_counts.get('quantity_fact', 0):,}."],
        [f"Physical-form fact rows: {row_counts.get('physical_form_fact', 0):,}."],
        ["Workbook built from cleaned notebook source data."],
    ]
    return headers, rows


def build_index_sheet(row_counts: dict[str, int]) -> tuple[list[str], list[list]]:
    headers = ["sheet_name", "purpose", "rows"]
    rows = [
        ["Entity Ontology Seed", "Combined company and chemical entity seed list", row_counts["ontology_entities"]],
        ["Entity Counts", "Count of ontology entities by type", row_counts["entity_counts"]],
        ["Checklist", "Normalization and table readiness checklist", row_counts["checklist"]],
        ["Company Table", "Canonical company dimension table", row_counts["company_table"]],
        ["Chemical Table", "Canonical chemical dimension table", row_counts["chemical_table"]],
        ["Company Activity Fact", "Company/chemical activity fact table", row_counts["company_activity_fact"]],
        ["Quantity Fact", "Long-form quantity table", row_counts["quantity_fact"]],
        ["Physical Form Fact", "Atomic physical-form rows", row_counts["physical_form_fact"]],
        ["Session Log", "Build notes and status", row_counts["session_log"]],
    ]
    return headers, rows


def write_workbook(path: Path, sheet_specs: list[dict]) -> dict[str, int]:
    counts: dict[str, int] = {}
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        for idx, spec in enumerate(sheet_specs, start=1):
            headers = spec["headers"]
            rows = spec["rows"]
            part_name = f"xl/worksheets/sheet{idx}.xml"
            log(f"Writing sheet {idx}: {spec['name']} ...")
            count = write_worksheet_xml(zf, part_name, spec["name"], headers, rows)
            counts[spec["key"]] = count
            log(f"Finished {spec['name']} with {count:,} data rows.")

        workbook_sheets = []
        rels = []
        content_overrides = []
        for idx, spec in enumerate(sheet_specs, start=1):
            workbook_sheets.append(
                f'<sheet name="{sanitize_xml_text(spec["name"])}" sheetId="{idx}" r:id="rId{idx}"/>'
            )
            rels.append(
                f'<Relationship Id="rId{idx}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet{idx}.xml"/>'
            )
            content_overrides.append(
                f'<Override PartName="/xl/worksheets/sheet{idx}.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
            )

        workbook_xml = (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
            'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
            "<sheets>"
            + "".join(workbook_sheets)
            + "</sheets>"
            "</workbook>"
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
            + "".join(content_overrides)
            + "</Types>"
        )
        root_rels = (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>'
            "</Relationships>"
        )
        core_props = (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" '
            'xmlns:dc="http://purl.org/dc/elements/1.1/" '
            'xmlns:dcterms="http://purl.org/dc/terms/" '
            'xmlns:dcmitype="http://purl.org/dc/dcmitype/" '
            'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">'
            "<dc:title>CDR Notebook Tables</dc:title>"
            "<dc:creator>Codex</dc:creator>"
            "<cp:lastModifiedBy>Codex</cp:lastModifiedBy>"
            f"<dcterms:created xsi:type=\"dcterms:W3CDTF\">{datetime.utcnow().isoformat(timespec='seconds')}Z</dcterms:created>"
            f"<dcterms:modified xsi:type=\"dcterms:W3CDTF\">{datetime.utcnow().isoformat(timespec='seconds')}Z</dcterms:modified>"
            "</cp:coreProperties>"
        )
        app_props = (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties" '
            'xmlns:vt="http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes">'
            "<Application>Microsoft Excel</Application>"
            "</Properties>"
        )

        zf.writestr("[Content_Types].xml", content_types)
        zf.writestr("_rels/.rels", root_rels)
        zf.writestr("xl/workbook.xml", workbook_xml)
        zf.writestr("xl/_rels/workbook.xml.rels", workbook_rels)
        zf.writestr("xl/styles.xml", styles_xml)
        zf.writestr("docProps/core.xml", core_props)
        zf.writestr("docProps/app.xml", app_props)
    return counts


def main() -> None:
    log(f"Source workbook CSV: {WORKING_CSV}")
    log(f"Raw CSV for column preview: {RAW_CSV}")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    company_headers, company_rows = build_company_table()
    chemical_headers, chemical_rows = build_chemical_table()
    ontology_headers, ontology_rows, ontology_counts = build_ontology_entities()
    checklist_headers, checklist_rows = build_checklist(has_physical_form_fact=True)
    company_activity_headers, company_activity_rows = build_company_activity_fact()
    quantity_headers, quantity_rows = build_quantity_fact()
    physical_form_headers, physical_form_rows = build_physical_form_fact()

    entity_count_headers = ["entity_type", "entity_count"]
    entity_count_rows = [[entity_type, count] for entity_type, count in sorted(ontology_counts.items())]

    session_headers = ["session_log"]
    session_rows = [
        ["Loaded source CSV and built workbook sheets."],
        ["Derived company and chemical dimension tables."],
        ["Derived ontology, checklist, activity, quantity, and physical-form tables."],
        ["Workbook generated from notebook-backed source data."],
    ]

    sheet_specs = [
        {"key": "ontology_entities", "name": "Entity Ontology Seed", "headers": ontology_headers, "rows": ontology_rows},
        {"key": "entity_counts", "name": "Entity Counts", "headers": entity_count_headers, "rows": entity_count_rows},
        {"key": "checklist", "name": "Checklist", "headers": checklist_headers, "rows": checklist_rows},
        {"key": "company_table", "name": "Company Table", "headers": company_headers, "rows": company_rows},
        {"key": "chemical_table", "name": "Chemical Table", "headers": chemical_headers, "rows": chemical_rows},
        {"key": "company_activity_fact", "name": "Company Activity Fact", "headers": company_activity_headers, "rows": company_activity_rows},
        {"key": "quantity_fact", "name": "Quantity Fact", "headers": quantity_headers, "rows": quantity_rows},
        {"key": "physical_form_fact", "name": "Physical Form Fact", "headers": physical_form_headers, "rows": physical_form_rows},
        {"key": "session_log", "name": "Session Log", "headers": session_headers, "rows": session_rows},
    ]

    counts = write_workbook(XLSX_PATH, sheet_specs)
    counts["entity_counts"] = len(entity_count_rows)
    counts["session_log"] = len(session_rows)
    counts["ontology_entities"] = len(ontology_rows)
    counts["checklist"] = len(checklist_rows)
    counts["company_table"] = len(company_rows)
    counts["chemical_table"] = len(chemical_rows)
    counts["company_activity_fact"] = counts.get("company_activity_fact", 0)
    counts["quantity_fact"] = counts.get("quantity_fact", 0)
    counts["physical_form_fact"] = counts.get("physical_form_fact", 0)

    index_headers, index_rows = build_index_sheet(counts)
    with zipfile.ZipFile(XLSX_PATH, "a", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        log("Writing index sheet ...")
        write_worksheet_xml(zf, "xl/worksheets/sheet1.xml", "Index", index_headers, index_rows)
        workbook_sheets = [
            '<sheet name="Index" sheetId="1" r:id="rId1"/>',
            '<sheet name="Entity Ontology Seed" sheetId="2" r:id="rId2"/>',
            '<sheet name="Entity Counts" sheetId="3" r:id="rId3"/>',
            '<sheet name="Checklist" sheetId="4" r:id="rId4"/>',
            '<sheet name="Company Table" sheetId="5" r:id="rId5"/>',
            '<sheet name="Chemical Table" sheetId="6" r:id="rId6"/>',
            '<sheet name="Company Activity Fact" sheetId="7" r:id="rId7"/>',
            '<sheet name="Quantity Fact" sheetId="8" r:id="rId8"/>',
            '<sheet name="Physical Form Fact" sheetId="9" r:id="rId9"/>',
            '<sheet name="Session Log" sheetId="10" r:id="rId10"/>',
        ]
        workbook_xml = (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
            'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
            "<sheets>"
            + "".join(workbook_sheets)
            + "</sheets>"
            "</workbook>"
        )
        workbook_rels = (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            + "".join(
                [
                    '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>',
                    '<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet2.xml"/>',
                    '<Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet3.xml"/>',
                    '<Relationship Id="rId4" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet4.xml"/>',
                    '<Relationship Id="rId5" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet5.xml"/>',
                    '<Relationship Id="rId6" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet6.xml"/>',
                    '<Relationship Id="rId7" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet7.xml"/>',
                    '<Relationship Id="rId8" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet8.xml"/>',
                    '<Relationship Id="rId9" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet9.xml"/>',
                    '<Relationship Id="rId10" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet10.xml"/>',
                    '<Relationship Id="rId99" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>',
                ]
            )
            + "</Relationships>"
        )
        content_types = (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
            '<Default Extension="xml" ContentType="application/xml"/>'
            '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
            '<Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>'
            + "".join(
                [
                    '<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>',
                    '<Override PartName="/xl/worksheets/sheet2.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>',
                    '<Override PartName="/xl/worksheets/sheet3.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>',
                    '<Override PartName="/xl/worksheets/sheet4.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>',
                    '<Override PartName="/xl/worksheets/sheet5.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>',
                    '<Override PartName="/xl/worksheets/sheet6.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>',
                    '<Override PartName="/xl/worksheets/sheet7.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>',
                    '<Override PartName="/xl/worksheets/sheet8.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>',
                    '<Override PartName="/xl/worksheets/sheet9.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>',
                    '<Override PartName="/xl/worksheets/sheet10.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>',
                ]
            )
            + "</Types>"
        )
        zf.writestr("[Content_Types].xml", content_types)
        zf.writestr("_rels/.rels", '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>')
        zf.writestr("xl/workbook.xml", workbook_xml)
        zf.writestr("xl/_rels/workbook.xml.rels", workbook_rels)
        zf.writestr("xl/styles.xml", (
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
        ))
        zf.writestr("docProps/core.xml", (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" '
            'xmlns:dc="http://purl.org/dc/elements/1.1/" '
            'xmlns:dcterms="http://purl.org/dc/terms/" '
            'xmlns:dcmitype="http://purl.org/dc/dcmitype/" '
            'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">'
            "<dc:title>CDR Notebook Tables</dc:title>"
            "<dc:creator>Codex</dc:creator>"
            "<cp:lastModifiedBy>Codex</cp:lastModifiedBy>"
            f"<dcterms:created xsi:type=\"dcterms:W3CDTF\">{datetime.utcnow().isoformat(timespec='seconds')}Z</dcterms:created>"
            f"<dcterms:modified xsi:type=\"dcterms:W3CDTF\">{datetime.utcnow().isoformat(timespec='seconds')}Z</dcterms:modified>"
            "</cp:coreProperties>"
        ))
        zf.writestr("docProps/app.xml", (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties" '
            'xmlns:vt="http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes">'
            "<Application>Microsoft Excel</Application>"
            "</Properties>"
        ))

    manifest = {
        "source_csv": str(WORKING_CSV),
        "raw_csv": str(RAW_CSV),
        "output_xlsx": str(XLSX_PATH),
        "counts": counts,
    }
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    log(f"Workbook written to {XLSX_PATH}")
    log(f"Manifest written to {MANIFEST_PATH}")


if __name__ == "__main__":
    main()

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
SOURCE_CSV = ROOT / "cleaned data" / "exports" / "2024 CDR Consumer and Commercial Use Information_clean_working_20260622_120407.csv"
OUTPUT_DIR = ROOT / "outputs" / f"company_site_chemical_{datetime.now():%Y%m%d_%H%M%S}"
XLSX_PATH = OUTPUT_DIR / "company_site_chemical_workbook.xlsx"
MANIFEST_PATH = OUTPUT_DIR / "build_manifest.json"


def log(message: str) -> None:
    print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] {message}", flush=True)


def normalize_text(value: str | None) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    text = unicodedata.normalize("NFKC", text).replace("\u00a0", " ")
    text = " ".join(text.split())
    return text or None


def is_blank(value: str | None) -> bool:
    return value is None or str(value).strip() == ""


def col_name(index_1_based: int) -> str:
    result = ""
    value = index_1_based
    while value:
        value, remainder = divmod(value - 1, 26)
        result = chr(65 + remainder) + result
    return result


def sanitize_xml_text(value: str) -> str:
    value = re.sub(r"[\x00-\x08\x0B\x0C\x0E-\x1F]", "", value)
    return xml_escape(value)


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


def read_rows(path: Path) -> Iterator[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        yield from reader


def write_sheet_xml(zf: zipfile.ZipFile, part_name: str, headers: list[str], rows: Iterable[list]) -> int:
    row_count = 1
    last_col = col_name(len(headers))
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


def normalize_row(row: dict[str, str], source_row_id: int) -> dict[str, str]:
    normalized = dict(row)
    normalized["source_row_id"] = source_row_id
    for column in [
        "standardized_parent_company_name",
        "foreign_parent_company_name",
        "domestic_parent_company_name",
        "chemical_name",
        "chemical_id",
        "chemical_id_w_o_dashes",
        "chemical_id_type",
        "site_name",
        "site_address_line1",
        "site_address_line2",
        "site_city",
        "site_county_parish",
        "site_state",
        "site_postal_code",
        "site_dun_bradstreet_number",
    ]:
        if column in row:
            normalized[f"{column}_normalized"] = normalize_text(row.get(column))
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
    seen: dict[str, list] = {}
    for source_row_id, row in enumerate(read_rows(SOURCE_CSV)):
        normalized = normalize_row(row, source_row_id)
        key = normalized.get("standardized_parent_company_name_normalized")
        if is_blank(key) or key in seen:
            continue
        seen[key] = [
            source_row_id,
            row.get("standardized_parent_company_name", ""),
            key,
            row.get("foreign_parent_company_name", ""),
            normalized.get("foreign_parent_company_name_normalized", ""),
            row.get("domestic_parent_company_name", ""),
            normalized.get("domestic_parent_company_name_normalized", ""),
            row.get("foreign_pc_dun_bradstreet_number", ""),
            row.get("domestic_pc_dun_bradstreet_number", ""),
        ]
    rows = list(seen.values())
    rows.sort(key=lambda item: (item[2] or "", item[1] or ""))
    return headers, rows


def build_site_table() -> tuple[list[str], list[list]]:
    headers = [
        "source_row_id",
        "company_key",
        "site_name_source",
        "site_key",
        "site_address_line1",
        "site_address_line2",
        "site_city",
        "site_county_parish",
        "site_state",
        "site_postal_code",
        "site_latitude",
        "site_longitude",
        "site_dun_bradstreet_number",
        "epa_tsca_program_id",
        "epa_facility_registry_id",
        "site_naics_code_1",
        "site_naics_activity_1",
    ]
    seen: dict[str, list] = {}
    for source_row_id, row in enumerate(read_rows(SOURCE_CSV)):
        normalized = normalize_row(row, source_row_id)
        company_key = normalized.get("standardized_parent_company_name_normalized")
        site_key_parts = [
            normalized.get("site_name_normalized"),
            normalized.get("site_address_line1_normalized"),
            normalized.get("site_city_normalized"),
            normalized.get("site_state_normalized"),
            normalized.get("site_postal_code_normalized"),
            normalized.get("site_dun_bradstreet_number_normalized"),
        ]
        site_key = " | ".join(part for part in site_key_parts if part)
        if is_blank(site_key) or site_key in seen:
            continue
        seen[site_key] = [
            source_row_id,
            company_key or "",
            row.get("site_name", ""),
            site_key,
            row.get("site_address_line1", ""),
            row.get("site_address_line2", ""),
            row.get("site_city", ""),
            row.get("site_county_parish", ""),
            row.get("site_state", ""),
            row.get("site_postal_code", ""),
            row.get("site_latitude", ""),
            row.get("site_longitude", ""),
            row.get("site_dun_bradstreet_number", ""),
            row.get("epa_tsca_program_id", ""),
            row.get("epa_facility_registry_id", ""),
            row.get("site_naics_code_1", ""),
            row.get("site_naics_activity_1", ""),
        ]
    rows = list(seen.values())
    rows.sort(key=lambda item: (item[3] or "", item[2] or ""))
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
    seen: dict[str, list] = {}
    for source_row_id, row in enumerate(read_rows(SOURCE_CSV)):
        normalized = normalize_row(row, source_row_id)
        key = normalized.get("chemical_id_w_o_dashes_normalized")
        if is_blank(key) or key in seen:
            continue
        seen[key] = [
            source_row_id,
            row.get("chemical_name", ""),
            normalized.get("chemical_name_normalized", ""),
            row.get("chemical_id", ""),
            normalized.get("chemical_id_normalized", ""),
            row.get("chemical_id_w_o_dashes", ""),
            key,
            row.get("chemical_id_type", ""),
            normalized.get("chemical_id_type_normalized", ""),
        ]
    rows = list(seen.values())
    rows.sort(key=lambda item: (item[6] or "", item[1] or ""))
    return headers, rows


def build_entity_list(entity_type: str, name_column: str, id_columns: list[str]) -> list[list]:
    rows: list[list] = []
    seen: set[tuple[str, str]] = set()
    for row in read_rows(SOURCE_CSV):
        name_value = normalize_text(row.get(name_column))
        if not name_value:
            continue
        normalized_ids = [normalize_text(row.get(column)) for column in id_columns if row.get(column)]
        normalized_ids = [value for value in normalized_ids if value]
        key_value = normalized_ids[0] if normalized_ids else name_value
        pair = (key_value, name_value)
        if pair in seen:
            continue
        seen.add(pair)
        output = [entity_type, key_value, name_value, ", ".join([name_column, *id_columns])]
        for column in id_columns:
            output.append(normalize_text(row.get(column)) or "")
        rows.append(output)
    rows.sort(key=lambda item: (item[2] or "", item[1] or ""))
    return rows


def build_ontology_seed() -> tuple[list[str], list[list]]:
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
    chemical_rows = build_entity_list(
        "chemical",
        "chemical_name",
        ["chemical_id", "chemical_id_w_o_dashes", "chemical_id_type"],
    )
    company_rows = build_entity_list(
        "company",
        "standardized_parent_company_name",
        [
            "foreign_parent_company_name",
            "domestic_parent_company_name",
            "foreign_pc_dun_bradstreet_number",
            "domestic_pc_dun_bradstreet_number",
        ],
    )
    rows: list[list] = []
    for row in chemical_rows:
        rows.append(row[:4] + [row[4], row[5], row[6], "", "", "", ""])
    for row in company_rows:
        rows.append(row[:4] + ["", "", "", row[4], row[5], row[6], row[7]])
    rows.sort(key=lambda item: (item[2] or "", item[1] or ""))
    return headers, rows


def build_entity_counts(ontology_rows: list[list]) -> tuple[list[str], list[list]]:
    headers = ["entity_type", "entity_count"]
    counts = Counter(row[0] for row in ontology_rows)
    rows = [[entity_type, count] for entity_type, count in sorted(counts.items())]
    return headers, rows


def build_checklist() -> tuple[list[str], list[list]]:
    headers = ["check", "status", "details"]
    columns = set(next(iter(read_rows(SOURCE_CSV))).keys())
    rows = [
        [
            "Encoding artifacts",
            "needs_review" if any(name.startswith("pf_ppv") for name in columns) else "ok",
            "Inspect any remaining mojibake in headers or range labels.",
        ],
        [
            "Company key",
            "ok" if "standardized_parent_company_name" in columns else "needs_review",
            "Use normalized parent company names as the primary company index key.",
        ],
        [
            "Chemical key",
            "ok" if "chemical_id_w_o_dashes" in columns else "needs_review",
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
                "ok" if code_column in columns and label_column in columns else "needs_review",
                "Keep code and label columns together until lookup validation is complete.",
            ]
        )
    sentinel_counts = {"CBI": 0, "NKRA": 0}
    for row in read_rows(SOURCE_CSV):
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
            "ok" if "source_row_id" in columns or True else "needs_review",
            "Every derived table should keep source_row_id for traceability.",
        ]
    )
    rows.append(
        [
            "Atomic physical forms",
            "ok",
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

    def rows() -> Iterator[list]:
        for source_row_id, row in enumerate(read_rows(SOURCE_CSV)):
            normalized = normalize_row(row, source_row_id)
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
        for source_row_id, row in enumerate(read_rows(SOURCE_CSV)):
            normalized = normalize_row(row, source_row_id)
            for quantity_column in quantity_columns:
                value = row.get(quantity_column, "")
                if is_blank(value):
                    continue
                rows_out = [
                    source_row_id,
                    normalized.get("standardized_parent_company_name_normalized", ""),
                    normalized.get("chemical_id_w_o_dashes_normalized", ""),
                    normalized.get("chemical_name_normalized", ""),
                    quantity_column,
                    value,
                    None,
                ]
                rows_out[6] = value.replace(",", "") if isinstance(value, str) else value
                yield rows_out

    return headers, rows()


def build_physical_form_fact() -> tuple[list[str], Iterator[list]]:
    headers = ["source_row_id", "chemical_name_key", "chemical_cas_key", "physical_form"]

    def rows() -> Iterator[list]:
        for source_row_id, row in enumerate(read_rows(SOURCE_CSV)):
            normalized = normalize_row(row, source_row_id)
            forms: list[str] = []
            raw_forms = row.get("physical_form_s_list", "")
            if not is_blank(raw_forms):
                forms = [normalize_text(part) for part in str(raw_forms).split(";")]
                forms = [value for value in forms if value]
            if not forms:
                forms = [column for column in row.keys() if column.startswith("pf_ppv") and not is_blank(row.get(column))]
            for form in forms:
                yield [
                    source_row_id,
                    normalized.get("chemical_name_normalized", ""),
                    normalized.get("chemical_id_w_o_dashes_normalized", ""),
                    form,
                ]

    return headers, rows()


def build_session_log(summary: dict[str, int]) -> tuple[list[str], list[list]]:
    headers = ["session_log"]
    rows = [
        ["Loaded cleaned source CSV."],
        [f"Unique companies: {summary['company_count']:,}."],
        [f"Unique sites: {summary['site_count']:,}."],
        [f"Unique chemicals: {summary['chemical_count']:,}."],
        [f"Filing fact rows: {summary['fact_count']:,}."],
        ["Workbook includes original notebook tabs plus separate company, site, and chemical profiles."],
    ]
    return headers, rows


def build_filing_fact() -> tuple[list[str], Iterator[list]]:
    headers = [
        "source_row_id",
        "company_key",
        "site_key",
        "chemical_cas_key",
        "chemical_name_key",
        "site_name_source",
        "chemical_name_source",
        "activity",
        "cons_and_or_comm_use",
        "used_in_prod_for_children",
        "percent_byproduct",
        "workers_reasonably_likely_exposed",
        "maximum_concentration",
        "consumer_commercial_product_category",
        "consumer_commercial_function_category",
        "joint_function_category",
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

    def rows() -> Iterator[list]:
        for source_row_id, row in enumerate(read_rows(SOURCE_CSV)):
            normalized = normalize_row(row, source_row_id)
            site_key_parts = [
                normalized.get("site_name_normalized"),
                normalized.get("site_address_line1_normalized"),
                normalized.get("site_city_normalized"),
                normalized.get("site_state_normalized"),
                normalized.get("site_postal_code_normalized"),
                normalized.get("site_dun_bradstreet_number_normalized"),
            ]
            site_key = " | ".join(part for part in site_key_parts if part)
            yield [
                source_row_id,
                normalized.get("standardized_parent_company_name_normalized", ""),
                site_key,
                normalized.get("chemical_id_w_o_dashes_normalized", ""),
                normalized.get("chemical_name_normalized", ""),
                row.get("site_name", ""),
                row.get("chemical_name", ""),
                row.get("activity", ""),
                row.get("cons_and_or_comm_use", ""),
                row.get("used_in_prod_for_children", ""),
                row.get("percent_byproduct", ""),
                row.get("workers_reasonably_likely_exposed", ""),
                row.get("maximum_concentration", ""),
                row.get("consumer_commercial_product_category", ""),
                row.get("consumer_commercial_function_category", ""),
                row.get("joint_function_category", ""),
                row.get("2023_domestic_pv", ""),
                row.get("2023_import_pv", ""),
                row.get("2023_pv", ""),
                row.get("2022_pv", ""),
                row.get("2021_pv", ""),
                row.get("2020_pv", ""),
                row.get("2023_v_used_on_site", ""),
                row.get("2023_v_exported", ""),
                row.get("2023_nationally_aggregated_pv", ""),
                row.get("2022_nationally_aggregated_pv", ""),
                row.get("2021_nationally_aggregated_pv", ""),
                row.get("2020_nationally_aggregated_pv", ""),
                row.get("c_c_pv_pct", ""),
            ]

    return headers, rows()


def build_index_rows(
    company_count: int,
    site_count: int,
    chemical_count: int,
    fact_count: int,
    ontology_count: int,
    activity_count: int,
    quantity_count: int,
    physical_count: int,
) -> tuple[list[str], list[list]]:
    headers = ["sheet_name", "purpose", "rows"]
    rows = [
        ["Entity Ontology Seed", "Combined company and chemical ontology seed list", ontology_count],
        ["Entity Counts", "Entity counts by ontology type", 2],
        ["Checklist", "Normalization and table readiness checklist", 11],
        ["Company Profiles", "Unique company dimension rows", company_count],
        ["Site Profiles", "Unique site dimension rows", site_count],
        ["Chemical Profiles", "Unique chemical dimension rows", chemical_count],
        ["Company Table", "Legacy company dimension tab from the original workbook", company_count],
        ["Chemical Table", "Legacy chemical dimension tab from the original workbook", chemical_count],
        ["Company Activity Fact", "Original activity fact table", activity_count],
        ["Quantity Fact", "Original long-form quantity table", quantity_count],
        ["Physical Form Fact", "Original atomic physical-form table", physical_count],
        ["Filing Fact", "One row per source filing row", fact_count],
        ["Session Log", "Build notes and status", 6],
        ["Source Notes", "Build notes and source description", 6],
    ]
    return headers, rows


def build_notes_rows(company_count: int, site_count: int, chemical_count: int, fact_count: int) -> tuple[list[str], list[list]]:
    headers = ["note"]
    rows = [
        [f"Workbook generated from {SOURCE_CSV.name}."],
        [f"Unique companies: {company_count:,}."],
        [f"Unique sites: {site_count:,}."],
        [f"Unique chemicals: {chemical_count:,}."],
        [f"Filing fact rows: {fact_count:,}."],
        ["Fact grain: one source row per company-site-chemical filing record."],
    ]
    return headers, rows


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
        'xmlns:dcterms="http://purl.org/dcterms/" '
        'xmlns:dcmitype="http://purl.org/dc/dcmitype/" '
        'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">'
        "<dc:title>Company-Site-Chemical Workbook</dc:title>"
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
    log(f"Source CSV: {SOURCE_CSV}")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    company_headers, company_rows = build_company_table()
    site_headers, site_rows = build_site_table()
    chemical_headers, chemical_rows = build_chemical_table()
    ontology_headers, ontology_rows = build_ontology_seed()
    entity_count_headers, entity_count_rows = build_entity_counts(ontology_rows)
    checklist_headers, checklist_rows = build_checklist()
    company_activity_headers, company_activity_rows = build_company_activity_fact()
    company_activity_rows_list = list(company_activity_rows)
    quantity_headers, quantity_rows = build_quantity_fact()
    quantity_rows_list = list(quantity_rows)
    physical_headers, physical_rows = build_physical_form_fact()
    physical_rows_list = list(physical_rows)
    filing_fact_headers, filing_fact_rows = build_filing_fact()
    fact_rows_list = list(filing_fact_rows)
    index_headers, index_rows = build_index_rows(
        len(company_rows),
        len(site_rows),
        len(chemical_rows),
        len(fact_rows_list),
        len(ontology_rows),
        len(company_activity_rows_list),
        len(quantity_rows_list),
        len(physical_rows_list),
    )
    notes_headers, notes_rows = build_notes_rows(len(company_rows), len(site_rows), len(chemical_rows), len(fact_rows_list))
    session_headers, session_rows = build_session_log(
        {
            "company_count": len(company_rows),
            "site_count": len(site_rows),
            "chemical_count": len(chemical_rows),
            "fact_count": len(fact_rows_list),
        }
    )

    sheet_specs = [
        {"name": "Index", "part_name": "xl/worksheets/sheet1.xml", "headers": index_headers, "rows": index_rows},
        {"name": "Entity Ontology Seed", "part_name": "xl/worksheets/sheet2.xml", "headers": ontology_headers, "rows": ontology_rows},
        {"name": "Entity Counts", "part_name": "xl/worksheets/sheet3.xml", "headers": entity_count_headers, "rows": entity_count_rows},
        {"name": "Checklist", "part_name": "xl/worksheets/sheet4.xml", "headers": checklist_headers, "rows": checklist_rows},
        {"name": "Company Profiles", "part_name": "xl/worksheets/sheet5.xml", "headers": company_headers, "rows": company_rows},
        {"name": "Site Profiles", "part_name": "xl/worksheets/sheet6.xml", "headers": site_headers, "rows": site_rows},
        {"name": "Chemical Profiles", "part_name": "xl/worksheets/sheet7.xml", "headers": chemical_headers, "rows": chemical_rows},
        {"name": "Company Table", "part_name": "xl/worksheets/sheet8.xml", "headers": company_headers, "rows": company_rows},
        {"name": "Chemical Table", "part_name": "xl/worksheets/sheet9.xml", "headers": chemical_headers, "rows": chemical_rows},
        {"name": "Company Activity Fact", "part_name": "xl/worksheets/sheet10.xml", "headers": company_activity_headers, "rows": company_activity_rows_list},
        {"name": "Quantity Fact", "part_name": "xl/worksheets/sheet11.xml", "headers": quantity_headers, "rows": quantity_rows_list},
        {"name": "Physical Form Fact", "part_name": "xl/worksheets/sheet12.xml", "headers": physical_headers, "rows": physical_rows_list},
        {"name": "Filing Fact", "part_name": "xl/worksheets/sheet13.xml", "headers": filing_fact_headers, "rows": fact_rows_list},
        {"name": "Session Log", "part_name": "xl/worksheets/sheet14.xml", "headers": session_headers, "rows": session_rows},
        {"name": "Source Notes", "part_name": "xl/worksheets/sheet15.xml", "headers": notes_headers, "rows": notes_rows},
    ]

    counts: dict[str, int] = {}
    with zipfile.ZipFile(XLSX_PATH, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        for spec in sheet_specs:
            log(f"Writing {spec['name']} ...")
            counts[spec["name"]] = write_sheet_xml(zf, spec["part_name"], spec["headers"], spec["rows"])
            log(f"Finished {spec['name']} with {counts[spec['name']]:,} data rows.")

    write_metadata(XLSX_PATH, sheet_specs)

    MANIFEST_PATH.write_text(
        json.dumps(
            {
                "source_csv": str(SOURCE_CSV),
                "output_xlsx": str(XLSX_PATH),
                "company_count": len(company_rows),
                "site_count": len(site_rows),
                "chemical_count": len(chemical_rows),
                "ontology_count": len(ontology_rows),
                "company_activity_count": len(company_activity_rows_list),
                "quantity_count": len(quantity_rows_list),
                "physical_count": len(physical_rows_list),
                "fact_count": len(fact_rows_list),
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    log(f"Workbook written to {XLSX_PATH}")
    log(f"Manifest written to {MANIFEST_PATH}")


if __name__ == "__main__":
    main()

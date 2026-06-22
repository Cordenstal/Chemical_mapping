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
OUTPUT_DIR = ROOT / "outputs" / f"all_companies_{datetime.now():%Y%m%d_%H%M%S}"
XLSX_PATH = OUTPUT_DIR / "all_companies_workbook.xlsx"
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


def build_company_rows() -> tuple[list[str], list[list]]:
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
        company_key = normalize_text(row.get("standardized_parent_company_name"))
        if is_blank(company_key) or company_key in seen:
            continue
        seen[company_key] = [
            source_row_id,
            row.get("standardized_parent_company_name", ""),
            company_key,
            row.get("foreign_parent_company_name", ""),
            normalize_text(row.get("foreign_parent_company_name")) or "",
            row.get("domestic_parent_company_name", ""),
            normalize_text(row.get("domestic_parent_company_name")) or "",
            row.get("foreign_pc_dun_bradstreet_number", ""),
            row.get("domestic_pc_dun_bradstreet_number", ""),
        ]
    rows = list(seen.values())
    rows.sort(key=lambda item: (item[2] or "", item[1] or ""))
    return headers, rows


def build_index_rows(company_count: int) -> tuple[list[str], list[list]]:
    headers = ["sheet_name", "purpose", "rows"]
    rows = [
        ["Company Profiles", "All unique company records extracted from the cleaned CDR source", company_count],
        ["Source Notes", "Build notes and source description", 4],
    ]
    return headers, rows


def build_notes_rows(company_count: int) -> tuple[list[str], list[list]]:
    headers = ["note"]
    rows = [
        [f"Workbook generated from {SOURCE_CSV.name}."],
        [f"Unique company records: {company_count:,}."],
        ["Deduplication key: standardized_parent_company_name."],
        ["Each row represents one unique company profile from the cleaned source data."],
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
        'xmlns:dcterms="http://purl.org/dc/terms/" '
        'xmlns:dcmitype="http://purl.org/dc/dcmitype/" '
        'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">'
        "<dc:title>All Companies Workbook</dc:title>"
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

    index_headers, _ = build_index_rows(0)
    notes_headers, notes_rows = build_notes_rows(0)
    company_headers, company_rows = build_company_rows()
    index_headers, index_rows = build_index_rows(len(company_rows))
    notes_headers, notes_rows = build_notes_rows(len(company_rows))

    sheet_specs = [
        {"name": "Index", "part_name": "xl/worksheets/sheet1.xml", "headers": index_headers, "rows": index_rows},
        {"name": "Company Profiles", "part_name": "xl/worksheets/sheet2.xml", "headers": company_headers, "rows": company_rows},
        {"name": "Source Notes", "part_name": "xl/worksheets/sheet3.xml", "headers": notes_headers, "rows": notes_rows},
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
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    log(f"Workbook written to {XLSX_PATH}")
    log(f"Manifest written to {MANIFEST_PATH}")


if __name__ == "__main__":
    main()

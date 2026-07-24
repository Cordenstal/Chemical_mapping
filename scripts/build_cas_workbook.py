from __future__ import annotations

import csv
import json
import math
import re
import zipfile
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from xml.sax.saxutils import escape as xml_escape


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "data" / "raw data" / "2024 CDR Consumer and Commercial Use Information.csv"
OUTPUT_DIR = ROOT / "outputs" / f"cas_workbook_{datetime.now():%Y%m%d_%H%M%S}"
OUTPUT_XLSX = OUTPUT_DIR / "2024_CDR_CAS_Profiles.xlsx"
MANIFEST = OUTPUT_DIR / "build_manifest.json"


def log(message: str) -> None:
    print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] {message}", flush=True)


def text(value: object) -> str:
    if value is None:
        return ""
    return " ".join(str(value).replace("\u00a0", " ").split())


def number(value: object):
    raw = text(value)
    if not raw or raw.upper() in {"CBI", "NKRA", "N/A", "NA"}:
        return None
    raw = raw.replace(",", "")
    try:
        result = float(raw)
        return int(result) if result.is_integer() else result
    except ValueError:
        return None


def col_name(index: int) -> str:
    result = ""
    while index:
        index, remainder = divmod(index - 1, 26)
        result = chr(65 + remainder) + result
    return result


def xml_text(value: object) -> str:
    return xml_escape(text(value), {'"': "&quot;", "'": "&apos;"})


def cell(ref: str, value: object, style: int = 0) -> str:
    if value is None or value == "":
        return ""
    style_attr = f' s="{style}"' if style else ""
    if isinstance(value, bool):
        return f'<c r="{ref}" t="b"{style_attr}><v>{1 if value else 0}</v></c>'
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
            return ""
        return f'<c r="{ref}"{style_attr}><v>{value}</v></c>'
    return f'<c r="{ref}" t="inlineStr"{style_attr}><is><t xml:space="preserve">{xml_text(value)}</t></is></c>'


DETAIL_COLUMNS = [
    "source_row_id",
    "CHEMICAL NAME",
    "CHEMICAL ID",
    "CHEMICAL ID W/O DASHES",
    "STANDARDIZED PARENT COMPANY NAME",
    "DOMESTIC PARENT COMPANY NAME",
    "SITE NAME",
    "SITE CITY",
    "SITE STATE",
    "ACTIVITY",
    "2023 DOMESTIC PV",
    "2023 IMPORT PV",
    "2023 PV",
    "2023 V EXPORTED",
    "2022 PV",
    "2021 PV",
    "2020 PV",
    "CHEM NEVER AT SITE",
    "2023 V USED ON-SITE",
    "PHYSICAL FORM(S) LIST",
    "CONSUMER / COMMERCIAL PRODUCT CATEGORY",
    "CONSUMER / COMMERCIAL FUNCTION CATEGORY",
    "JOINT FUNCTION CATEGORY",
    "CONS AND/OR COMM USE",
    "USED IN PROD FOR CHILDREN",
    "C / C PV PCT",
    "MAXIMUM CONCENTRATION",
    "WORKERS REASONABLY LIKELY EXPOSED",
    "COMMERCIAL WORKERS REASONABLY LIKELY EXPOSED",
]


def read_source() -> tuple[list[str], list[dict[str, str]]]:
    log(f"Reading source CSV: {SOURCE}")
    with SOURCE.open("r", encoding="cp1252", newline="") as handle:
        reader = csv.DictReader(handle)
        headers = reader.fieldnames or []
        rows = []
        for idx, raw in enumerate(reader, start=2):
            row = {key: text(value) for key, value in raw.items()}
            row["source_row_id"] = idx
            rows.append(row)
            if idx % 10000 == 0:
                log(f"Read {idx - 1:,} data rows")
    log(f"Finished reading {len(rows):,} rows and {len(headers):,} columns")
    return headers, rows


def sheet_name(cas: str, used: set[str]) -> str:
    base = re.sub(r"[\\/*?:\[\]]", "_", cas)[:31] or "CAS"
    candidate = base
    suffix = 1
    while candidate in used:
        suffix_text = f"_{suffix}"
        candidate = (base[: 31 - len(suffix_text)] + suffix_text)
        suffix += 1
    used.add(candidate)
    return candidate


def aggregate(cas: str, rows: list[dict[str, str]]) -> dict[str, object]:
    def total(column: str):
        values = [number(row.get(column)) for row in rows]
        values = [value for value in values if value is not None]
        return sum(values) if values else None

    def unique(column: str, limit: int = 8) -> str:
        values = sorted({text(row.get(column)) for row in rows if text(row.get(column))})
        if len(values) > limit:
            return "; ".join(values[:limit]) + f"; +{len(values) - limit} more"
        return "; ".join(values)

    return {
        "CAS": cas,
        "chemical_name": unique("CHEMICAL NAME"),
        "record_count": len(rows),
        "total_product_2023": total("2023 PV"),
        "total_import_2023": total("2023 IMPORT PV"),
        "total_export_2023": total("2023 V EXPORTED"),
        "total_domestic_2023": total("2023 DOMESTIC PV"),
        "total_used_on_site_2023": total("2023 V USED ON-SITE"),
        "total_product_2022": total("2022 PV"),
        "total_product_2021": total("2021 PV"),
        "total_product_2020": total("2020 PV"),
        "parent_companies": unique("STANDARDIZED PARENT COMPANY NAME"),
        "sites": unique("SITE NAME"),
        "activities": unique("ACTIVITY"),
    }


def sheet_xml(title: str, headers: list[str], rows: list[list[object]], title_style: int = 2) -> str:
    last_col = col_name(max(1, len(headers)))
    last_row = max(1, len(rows) + 1)
    parts = [
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">',
        '<sheetViews><sheetView workbookViewId="0"><pane ySplit="1" topLeftCell="A2" activePane="bottomLeft" state="frozen"/><selection pane="bottomLeft" activeCell="A1" sqref="A1"/></sheetView></sheetViews>',
        '<sheetFormatPr defaultRowHeight="15"/>',
        '<sheetData>',
    ]
    for row_index, row in enumerate(rows, start=1):
        parts.append(f'<row r="{row_index}">')
        for col_index, value in enumerate(row, start=1):
            style = title_style if row_index == 1 else (1 if row_index == 2 else 0)
            parts.append(cell(f"{col_name(col_index)}{row_index}", value, style))
        parts.append("</row>")
    parts.extend(["</sheetData>", f'<autoFilter ref="A1:{last_col}{last_row}"/>', "</worksheet>"])
    return "".join(parts)


def styles_xml() -> str:
    return '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
<fonts count="3"><font><sz val="11"/><color theme="1"/><name val="Calibri"/><family val="2"/></font><font><b/><color rgb="FFFFFFFF"/><sz val="11"/><name val="Calibri"/><family val="2"/></font><font><b/><color rgb="FF1F1F1F"/><sz val="14"/><name val="Calibri"/><family val="2"/></font></fonts>
<fills count="4"><fill><patternFill patternType="none"/></fill><fill><patternFill patternType="gray125"/></fill><fill><patternFill patternType="solid"><fgColor rgb="FF1F4E78"/><bgColor indexed="64"/></patternFill></fill><fill><patternFill patternType="solid"><fgColor rgb="FFD9EAF7"/><bgColor indexed="64"/></patternFill></fill></fills>
<borders count="1"><border><left/><right/><top/><bottom/><diagonal/></border></borders>
<cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>
<cellXfs count="3"><xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/><xf numFmtId="0" fontId="1" fillId="2" borderId="0" xfId="0" applyFont="1" applyFill="1"/><xf numFmtId="0" fontId="2" fillId="3" borderId="0" xfId="0" applyFont="1" applyFill="1"/></cellXfs>
<cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles>
</styleSheet>'''


def package_metadata(sheet_specs: list[tuple[str, str]]) -> dict[str, str]:
    sheets = "".join(f'<sheet name="{xml_text(name)}" sheetId="{idx}" r:id="rId{idx}"/>' for idx, (name, _) in enumerate(sheet_specs, start=1))
    rels = "".join(f'<Relationship Id="rId{idx}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet{idx}.xml"/>' for idx, _ in enumerate(sheet_specs, start=1))
    overrides = "".join(f'<Override PartName="/xl/worksheets/sheet{idx}.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>' for idx, _ in enumerate(sheet_specs, start=1))
    workbook = f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?><workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets>{sheets}</sheets></workbook>'''
    workbook_rels = f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">{rels}<Relationship Id="rIdStyles" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/></Relationships>'''
    content_types = f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/><Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>{overrides}</Types>'''
    root_rels = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>'''
    return {"xl/workbook.xml": workbook, "xl/_rels/workbook.xml.rels": workbook_rels, "[Content_Types].xml": content_types, "_rels/.rels": root_rels}


def main() -> None:
    started = datetime.now()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    headers, rows = read_source()
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        grouped[text(row.get("CHEMICAL ID W/O DASHES"))].append(row)
    log(f"Grouped source into {len(grouped):,} CAS values")

    summaries = []
    sheet_rows: list[tuple[str, str]] = []
    used_names: set[str] = set()
    summary_headers = ["CAS", "chemical_name", "record_count", "total_product_2023", "total_import_2023", "total_export_2023", "total_domestic_2023", "total_used_on_site_2023", "total_product_2022", "total_product_2021", "total_product_2020", "parent_companies", "sites", "activities"]
    detail_headers = DETAIL_COLUMNS
    for index, cas in enumerate(sorted(grouped), start=1):
        summary = aggregate(cas, grouped[cas])
        summaries.append(summary)
        tab = sheet_name(grouped[cas][0].get("CHEMICAL ID", cas), used_names)
        sheet_rows.append((tab, cas))
        if index % 500 == 0:
            log(f"Prepared {index:,}/{len(grouped):,} CAS profiles")

    specs = [("Summary", "summary"), ("Data Dictionary", "dictionary")] + [(name, cas) for name, cas in sheet_rows]
    metadata = package_metadata(specs)
    log(f"Writing workbook with {len(specs):,} worksheets")
    with zipfile.ZipFile(OUTPUT_XLSX, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for path, content in metadata.items():
            archive.writestr(path, content)
        archive.writestr("xl/styles.xml", styles_xml())
        summary_rows = [summary_headers]
        for summary in summaries:
            summary_rows.append([summary.get(key) for key in summary_headers])
        archive.writestr("xl/worksheets/sheet1.xml", sheet_xml("Summary", summary_headers, summary_rows))
        dictionary_rows = [["Field", "Meaning"], ["total_product_2023", "Sum of 2023 PV across all source records for the CAS."], ["total_import_2023", "Sum of 2023 IMPORT PV across all source records for the CAS."], ["total_export_2023", "Sum of 2023 V EXPORTED across all source records for the CAS."], ["record_count", "Number of source rows associated with the CAS."], ["source_row_id", "Original CSV data-row number, including the header as row 1."]]
        archive.writestr("xl/worksheets/sheet2.xml", sheet_xml("Data Dictionary", ["Field", "Meaning"], dictionary_rows))
        for index, (tab, cas) in enumerate(sheet_rows, start=3):
            profile = aggregate(cas, grouped[cas])
            profile_rows = [[f"CAS Profile: {cas}", "", "", ""], ["Metric", "Value", "Notes", ""], ["Chemical name", profile["chemical_name"], "Unique names found in source records", ""], ["Record count", profile["record_count"], "Source records for this CAS", ""], ["Total product 2023", profile["total_product_2023"], "Sum of 2023 PV", ""], ["Total import 2023", profile["total_import_2023"], "Sum of 2023 IMPORT PV", ""], ["Total export 2023", profile["total_export_2023"], "Sum of 2023 V EXPORTED", ""], ["Parent companies", profile["parent_companies"], "Unique values, abbreviated if numerous", ""], ["Sites", profile["sites"], "Unique values, abbreviated if numerous", ""], ["Activities", profile["activities"], "Unique values, abbreviated if numerous", ""], [], detail_headers]
            for row in grouped[cas]:
                profile_rows.append([row.get(column, "") if column not in {"2023 DOMESTIC PV", "2023 IMPORT PV", "2023 PV", "2023 V EXPORTED", "2022 PV", "2021 PV", "2020 PV", "2023 V USED ON-SITE"} else (number(row.get(column)) if number(row.get(column)) is not None else row.get(column, "")) for column in detail_headers])
            archive.writestr(f"xl/worksheets/sheet{index}.xml", sheet_xml(tab, detail_headers, profile_rows))
            if (index - 2) % 500 == 0:
                log(f"Wrote {index - 2:,}/{len(sheet_rows):,} CAS worksheets")

    manifest = {"source": str(SOURCE), "output": str(OUTPUT_XLSX), "rows": len(rows), "columns": len(headers), "unique_cas": len(grouped), "summary_columns": summary_headers, "detail_columns": detail_headers, "encoding_used": "cp1252", "started": started.isoformat(), "finished": datetime.now().isoformat()}
    MANIFEST.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    log(f"Workbook written: {OUTPUT_XLSX}")
    log(f"Manifest written: {MANIFEST}")


if __name__ == "__main__":
    main()

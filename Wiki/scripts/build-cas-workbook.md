# CAS Profile Workbook Builder

- Script: `scripts/build_cas_workbook.py`
- Source: `data/raw data/2024 CDR Consumer and Commercial Use Information.csv`
- Output: `outputs/cas_workbook_*/2024_CDR_CAS_Profiles.xlsx`
- Purpose: Build a review workbook with a summary row and dedicated worksheet for every unique CAS value.

## Processing

- Reads the raw Windows-1252 CSV without modifying it.
- Preserves CAS identifiers as text and keeps original source row numbers.
- Converts exact numeric volume fields to numeric cells when possible.
- Aggregates `2023 PV` as total product, `2023 IMPORT PV` as imports, and `2023 V EXPORTED` as exports.
- Creates `Summary`, `Data Dictionary`, and one worksheet per CAS value.
- Emits timestamped progress logging and a JSON build manifest.

## Validation

- Workbook package and worksheet XML are parsed after creation.
- Workbook is opened with `openpyxl` to verify sheet count and representative values.
- Sample totals are independently recomputed from the source CSV.

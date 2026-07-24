# 2024 CDR CAS Profile Workbook

- Artifact pattern: `outputs/cas_workbook_*/2024_CDR_CAS_Profiles.xlsx`
- Source: `data/raw data/2024 CDR Consumer and Commercial Use Information.csv`
- Build script: [Build CAS Profile Workbook Builder](../scripts/build-cas-workbook.md)

## Workbook structure

- `Summary`: one row per unique CAS with product, import, export, record-count, company, site, and activity summaries.
- `Data Dictionary`: definitions for the calculated fields and provenance fields.
- CAS worksheets: detailed source records and a profile summary for each CAS number.

The workbook uses `2023 PV` for total product, `2023 IMPORT PV` for imports, and `2023 V EXPORTED` for exports. Totals are sums of numeric source values; nonnumeric sentinel values such as `CBI` and `NKRA` remain visible in the detail tabs and are not included in numeric sums.

## Latest build

- Source rows: 64,023
- Source columns: 85
- Unique CAS values: 8,553
- Worksheets: 8,555
- Source encoding used: Windows-1252

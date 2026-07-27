# 2024 CDR Consumer and Commercial Use Information Clean CSV

- Canonical source path: `cleaned data/2024 CDR Consumer and Commercial Use Information_clean.csv`
- Source type: cleaned CSV export
- Why it matters: this is the working dataset that needs normalization before it can be treated as a stable workbook or relational source.
- Key points:
  - 64,024 lines and 85 columns.
  - Contains core chemical, company, site, and consumer/commercial use data in one wide table.
  - Uses code/description pairs, sparse conditional columns, and several multi-valued fields.
  - Includes encoding artifacts such as `â€“` in range labels.
- Update triggers:
  - Any further cleaning of the CSV.
  - Any schema split, workbook conversion, or workbook-level transformation based on this file.
  - Any change to column names, code domains, or encoding fixes.
- Last reviewed date: 2026-06-18

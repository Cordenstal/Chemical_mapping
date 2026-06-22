# All Companies Workbook Builder

- Canonical source path: `scripts/build_all_companies_workbook.py`
- Source type: Python automation
- Purpose: build a compact workbook that lists every unique company profile from the cleaned CDR source CSV.
- Output:
  - `outputs/all_companies_YYYYMMDD_HHMMSS/all_companies_workbook.xlsx`
  - `outputs/all_companies_YYYYMMDD_HHMMSS/build_manifest.json`
- Workbook sheets:
  - `Index`
  - `Company Profiles`
  - `Source Notes`
- Debugging notes:
  - The script logs each sheet write and final file location with timestamps.
  - The company sheet is deduplicated by normalized `standardized_parent_company_name`.

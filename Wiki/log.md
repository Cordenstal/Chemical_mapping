# Wiki Log

## 2026-06-17

- Bootstrapped the baseline repository template.
- Created root governance files, wiki pages, ignore rules, README, git metadata, and `.venv/`.
- Normalized the root README title to `Excel Project` so the baseline matches the workspace name.

## 2026-06-18

- Added a canonical source page for `cleaned data/2024 CDR Consumer and Commercial Use Information_clean.csv`.
- Added a normalization plan covering encoding fixes, lookup-table splits, multi-valued field handling, datatype cleanup, and target table decomposition.
- Synced the wiki index to include the new source and plan pages.
- Built a Jupyter notebook scaffold for practicing CDR CSV cleaning with progress logging, audit checks, normalization helpers, and an export template.
- Added a canonical wiki page for `jupyter notebook 1.ipynb` and synced the wiki index.

## 2026-06-19

- Extended `jupyter notebook 1.ipynb` with ontology seed extraction for chemical and company entities.
- Added a canonical wiki page for the notebook-derived entity ontology seed and synced the wiki index.
- Extended the notebook pipeline to normalize company names, normalize chemical IDs, unpivot long-form quantity facts, split physical forms into atomic rows, and preserve `source_row_id` provenance.
- Updated the ontology seed wiki page and related notebook documentation to reflect the expanded extraction pipeline.
- Added a pre-table normalization checklist to the notebook and created a matching wiki page for the remaining cleanup gates.
- Added starter canonical table outputs for companies, chemicals, company-chemical activity facts, quantity facts, and physical-form facts.
- Added a wiki page describing the starter normalized table model and updated related notebook documentation.
- Fixed the notebook schema drift so the workbook executes end to end with standardized lower-case source columns and retained raw quantity values.

## 2026-06-20

- Added a recursive ComfyUI custom-node dependency installer script with timestamped progress logging and end-of-run failure reporting.
- Added a canonical wiki page for the installer script and synced the wiki index.
- Updated the automation status wiki page to reflect the new script.

## 2026-06-20

- Relocated the ComfyUI dependency installer to the portable root and changed it to resolve `ComfyUI\custom_nodes` relative to its own location.

## 2026-06-22

- Added `scripts/build_all_companies_workbook.py` to generate a workbook of all unique company profiles from the cleaned CDR source CSV.
- Added a canonical wiki page for the all-companies workbook builder and synced the wiki index.
- Generated `outputs/all_companies_20260622_132445/all_companies_workbook.xlsx` with `Index`, `Company Profiles`, and `Source Notes` sheets.
- Added `scripts/build_company_site_chemical_workbook.py` to generate a workbook with separate company, site, chemical, and filing-fact dataframes from the cleaned CDR source CSV.
- Added a canonical wiki page for the company-site-chemical workbook builder and synced the wiki index.
- Generated `outputs/company_site_chemical_20260622_133515/company_site_chemical_workbook.xlsx` with the original notebook tabs plus `Company Profiles`, `Site Profiles`, `Chemical Profiles`, and `Filing Fact` sheets.

## 2026-07-10

- Added `scripts/build_cas_workbook.py` with timestamped progress logging for raw CDR-to-CAS workbook generation.
- Generated `outputs/cas_workbook_20260710_104038/2024_CDR_CAS_Profiles.xlsx` from the raw Windows-1252 CSV.
- Generated 8,555 worksheets: `Summary`, `Data Dictionary`, and one tab for each of 8,553 unique CAS values.
- Added the CAS workbook artifact documentation and synchronized the wiki index.

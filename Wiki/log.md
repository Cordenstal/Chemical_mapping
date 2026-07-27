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

## 2026-07-24

- Preserved the existing Git history and renamed the primary local branch from `master` to `main`.
- Confirmed that no Git remote is configured.
- Updated the repository root page and wiki baseline state to match the Git configuration.
- Added `scripts/build_cdr_mapping_data.py` for Phase 1 raw CDR ingestion, CBI-safe normalization, coordinate validation, and SQLite/CSV outputs.
- Generated `outputs/cdr_mapping_phase1_20260724_111106/` with sanitized normalized tables, a queryable SQLite database, a build manifest, and quality reports.
- Added canonical wiki pages for the Phase 1 importer and mapping data layer, and synchronized the wiki index.
- Added `scripts/build_cdr_spatial_layer.py` for Phase 2 coordinate validation, public GeoJSON generation, location audits, state summaries, and SQLite spatial indexing.
- Generated `outputs/cdr_mapping_phase2_20260724_112247/` with 50,056 public record points and 4,279 public facility points; excluded CBI locations and invalid null-island coordinates.
- Added canonical wiki pages for the Phase 2 spatial layer and synchronized the wiki index.
- Regenerated the canonical Phase 1 output as `outputs/cdr_mapping_phase1_20260724_112422/` after restoring `source_row_id` provenance in the CSV export, then regenerated Phase 2 as `outputs/cdr_mapping_phase2_20260724_112508/`.
- Interim Phase 1/Phase 2 test output directories were removed; the latest paths above are the retained artifacts.
- Added `scripts/build_cdr_mapping_dashboard.py` to package the Phase 2 public spatial layer into a portable interactive dashboard with chemical search, facility/activity filters, clustered points, USGS basemaps, and CBI-safe detail panels.
- Generated `outputs/cdr_mapping_phase3_20260724_113402/` with a 7,404-chemical search index and the dashboard application assets.
- Numeric production/import/use values remain excluded; CBI locations remain countable but unmapped.
- Added canonical Phase 3 dashboard documentation and synchronized the wiki index.
- Fixed the Phase 3 dashboard refresh error caused by an out-of-scope record collection, switched source-record points to canvas rendering, and added debounced filter refreshes to prevent block-like map rendering under large result sets.
- Regenerated the dashboard package as `outputs/cdr_mapping_phase3_20260724_115050/`.
- Diagnosed the screenshot showing disjoint basemap tiles: the page was opened from `file://`, which blocked data fetches, and Leaflet's external layout stylesheet was not reliably applied. Added an embedded `dashboard_data.js` fallback, removed fragile stylesheet/script integrity checks, and added local critical Leaflet tile-positioning rules.
- Regenerated the dashboard package as `outputs/cdr_mapping_phase3_20260724_120039/` and synchronized the previous handoff directory with the repaired assets.
- Corrected facility marker classification to aggregate activities across each facility's public records: Manufacture-only uses blue, Import-only uses orange, and mixed/other activity uses green for Other / Combined.
- Regenerated the dashboard package as `outputs/cdr_mapping_phase3_20260724_125130/` and synchronized previously handed-off dashboard paths.

## 2026-07-27

- Removed the superseded CDR workbook output `outputs/cdr_workbook_20260622_123715/`; retained `outputs/cdr_workbook_20260622_123812/`.
- Removed the superseded company-site workbook output `outputs/company_site_chemical_20260622_132703/`; retained `outputs/company_site_chemical_20260622_133515/`.
- Removed the stale OpenOffice lock file from the retained CAS workbook output.
- Confirmed the retained output families are `all_companies_20260622_132445`, `cas_workbook_20260710_104038`, `cdr_workbook_20260622_123812`, `company_site_chemical_20260622_133515`, and `cdr_mapping`.
- Replaced the baseline root README with a professional Chemical Mapping project overview covering the end-to-end pipeline, setup commands, generated outputs, data-quality controls, CBI-safe handling, and responsible-use limitations.
- Synchronized the README source page, repository snapshot, repository-root page, and wiki current-state summary.

# Chemical Mapping

Chemical Mapping is a Python data-engineering and analytics project that transforms the EPA's 2024 Chemical Data Reporting (CDR) dataset into a structured, searchable, and visual analytical resource.

The project is designed around a practical problem: regulatory reporting data is valuable but difficult to explore when chemical names, CAS numbers, company names, facility records, encodings, coordinates, and disclosure values are inconsistent. This repository builds a repeatable path from raw reporting records to reviewable analytical outputs.

The result is a decision-support and data-exploration system for comparing chemical activity across chemicals, companies, facilities, states, and geographic regions. It is not an environmental risk assessment and does not infer risk, exposure, or compliance conclusions.

## What the project produces

- Normalized record, chemical, facility, volume-fact, and field-status tables
- A queryable SQLite data layer with source-row provenance
- CAS-level chemical profile workbooks
- Company, site, chemical, filing-fact, and quantity workbooks
- Company profile workbooks for broad organization-level review
- Public facility and reporting-record GeoJSON layers
- State summaries, location audits, unmapped-record extracts, and quality reports
- A local interactive dashboard with chemical search, activity filters, clustered map views, and CBI-safe detail panels
- JSON build manifests that record source lineage, output files, and policy decisions

## Pipeline at a glance

```text
EPA 2024 CDR CSV
        |
        v
Phase 1: ingest, clean, normalize, validate, and model
        |
        +--> CSV tables + SQLite + quality reports
        |
        v
Phase 2: validate public coordinates and prepare spatial layers
        |
        +--> GeoJSON + spatial SQLite + state/location audits
        |
        v
Phase 3: package searchable dashboard assets
        |
        +--> local HTML/CSS/JavaScript dashboard

Parallel workbook builders
        |
        +--> CAS, company, site, chemical, quantity, and filing workbooks
```

## Workflow

### 1. Ingest and normalize

`build_cdr_mapping_data.py` reads the raw Windows-1252 CDR export and preserves the source-row key. It cleans text, normalizes chemical identifiers and names, standardizes company and facility fields, classifies disclosure values, validates coordinates, and creates preliminary facility keys from public site identity fields.

The Phase 1 output includes long-form volume facts for production, imports, exports, domestic use, and on-site use fields where source values are available. Sensitive sentinel values such as CBI, NKRA, and not-applicable values are blanked in derived value fields and retained as field-level statuses rather than treated as numbers.

### 2. Build analytical models and workbooks

The workbook builders create practical review products from the raw or cleaned CDR extracts:

- CAS profile workbooks with summary and CAS-specific worksheets
- Company, site, chemical, activity, quantity, physical-form, and filing-fact tables
- All-company profile workbooks for organization-level review
- Notebook-style analytical tables with retained source-row provenance

These outputs make it possible to inspect records at multiple grains instead of forcing every question into one wide source table.

### 3. Prepare spatial data

`build_cdr_spatial_layer.py` converts eligible public coordinates into facility-level and source-record-level GeoJSON. It also generates location audits, unmapped-record extracts, state summaries, a spatial SQLite index, and machine-readable and human-readable quality reports.

The spatial stage rejects missing, invalid, and `(0, 0)` null-island coordinates. CBI locations are summarized as indicators but are not inferred or plotted.

### 4. Package the dashboard

`build_cdr_mapping_dashboard.py` packages the latest Phase 2 artifacts into a portable local dashboard. The dashboard supports chemical/CAS search, facility and activity filters, clustered facility and source-record views, activity-based marker classification, source-row detail, and selectable USGS basemaps.

The package includes an embedded data fallback so `index.html` can be opened directly, although a local HTTP server is recommended for larger browser sessions.

### 5. Validate and review

Every major build emits progress logging, a `build_manifest.json`, and quality findings. The pipeline identifies incomplete, unmapped, conflicting, and candidate duplicate records for review rather than silently dropping or collapsing them.

## Repository layout

```text
data/raw data/       Raw EPA CDR source CSV
cleaned data/        Encoding-cleaned and working CSV extracts
scripts/             Python pipeline and workbook builders
outputs/             Generated workbooks, data layers, reports, and dashboard packages
app/                 Dashboard source assets
images/              Workbook screenshots and visual references
Wiki/                Project documentation, schemas, and build notes
jupyter notebook 1.ipynb
                     Cleaning and normalization practice notebook
```

## Requirements

- Python 3.10 or newer
- A browser for the dashboard
- Network access from the browser if loading external Leaflet, MarkerCluster, and USGS basemap assets

The pipeline scripts use the Python standard library for CSV, JSON, SQLite, ZIP/XML workbook generation, filesystem, and command-line work. No `requirements.txt` is currently needed for the committed scripts.

## Quick start

From the repository root:

```text
python scripts/build_cdr_mapping_data.py
python scripts/build_cdr_spatial_layer.py
python scripts/build_cdr_mapping_dashboard.py
```

The scripts automatically discover the latest prior phase output and create timestamped directories under `outputs/`.

To run the dashboard, serve the generated Phase 3 directory locally:

```text
python -m http.server 8000 --directory outputs/cdr_mapping_phase3_YYYYMMDD_HHMMSS
```

Then open <http://localhost:8000/>.

### Explicit phase paths

Use explicit paths when reproducibility or reruns require a fixed input and output directory:

```text
python scripts/build_cdr_mapping_data.py \
  --source "data/raw data/2024 CDR Consumer and Commercial Use Information.csv" \
  --encoding cp1252 \
  --output-dir outputs/cdr_mapping_phase1_run

python scripts/build_cdr_spatial_layer.py \
  --phase1-dir outputs/cdr_mapping_phase1_run \
  --output-dir outputs/cdr_mapping_phase2_run

python scripts/build_cdr_mapping_dashboard.py \
  --phase2-dir outputs/cdr_mapping_phase2_run \
  --output-dir outputs/cdr_mapping_phase3_run
```

## Workbook builders

These scripts run independently from the mapping phases and write timestamped workbooks under `outputs/`:

```text
python scripts/build_cas_workbook.py
python scripts/build_all_companies_workbook.py
python scripts/build_company_site_chemical_workbook.py
python scripts/build_cdr_workbook.py
```

The corresponding workbook documentation is available in [`Wiki/index.md`](Wiki/index.md), including the expected sheet structure and source grain for each builder.

## Data quality and interpretation

This project treats data quality as part of the product, not as a final afterthought.

- `source_row_id` preserves a link back to the input record.
- Required headers, row counts, extra columns, coordinate validity, disclosure statuses, and candidate duplicate groups are checked.
- FRS values represented in scientific notation are retained as disclosed text and are not treated as exact join keys without independent verification.
- Candidate duplicate groups are reported but not automatically deduplicated. This protects against incorrectly aggregating distinct reporting facts.
- The spatial layers contain public coordinates and CBI-safe indicators, not inferred facility locations.
- The dashboard does not display numeric production, import, export, or use values. Numeric map symbology remains deferred until duplicate-grain review is complete.

For detailed findings, inspect the `quality_report.txt`, `quality_report.json`, `unmapped_records.csv`, `location_audit.csv`, and `build_manifest.json` files in each generated output directory.

## Technical skills demonstrated

- Python data processing and repeatable ETL workflows
- Text, encoding, identifier, and entity normalization
- Chemical/CAS, company, facility, and site modeling
- Analytical aggregation and long-form fact-table design
- Excel workbook generation and validation
- SQLite data packaging and queryable local artifacts
- GeoJSON and geospatial data preparation
- Interactive dashboard development with HTML, CSS, and JavaScript
- Data-quality profiling, provenance, audit reporting, and review workflows

## Scope and responsible use

The outputs are intended to make CDR reporting data easier to explore, compare, validate, and use in downstream analysis. They should be interpreted as transformed reporting data and analytical aids. They are not a substitute for source-document review, verified facility resolution, regulatory interpretation, environmental risk assessment, or exposure analysis.

## Documentation

The [`Wiki/`](Wiki/) directory is the repository's detailed knowledge base. Start with [`Wiki/index.md`](Wiki/index.md) for the catalog of pipeline phases, schemas, source notes, workbook builders, and project history.

## Takeaway

Chemical Mapping turns a difficult regulatory CSV into a traceable set of analytical tables, workbooks, spatial layers, quality reports, and an interactive map—showing how careful data engineering can make complex information more usable for real decisions.

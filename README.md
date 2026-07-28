# Chemical Mapping

Chemical Mapping turns the EPA's 2024 Chemical Data Reporting (CDR) CSV into normalized data, spatial outputs, and a browser-based dashboard for exploring public chemical reporting locations.

The dashboard is a local, file-based application. There is no application server in this repository, and no local HTTP server is required to open it.

## Repository layout

```text
data/raw data/                  Original EPA CDR CSV
cleaned data/                   Encoding-cleaned and working CSV files
scripts/                        Three CDR mapping pipeline scripts
app/cdr_mapping_dashboard/     Dashboard source and checked-in data assets
outputs/                        Generated workbooks, dashboard artifacts, and reports
images/                         Workbook screenshots and visual references
Wiki/                           Project documentation and change history
jupyter notebook 1.ipynb        CDR cleaning and normalization practice notebook
```

The active scripts are:

- `scripts/build_cdr_mapping_data.py` — reads the raw CDR CSV, normalizes records, preserves `source_row_id`, classifies disclosure values, validates coordinates, and writes CSV/SQLite data plus quality reports.
- `scripts/build_cdr_spatial_layer.py` — converts eligible public coordinates into facility and source-record GeoJSON, state summaries, unmapped-record extracts, a SQLite spatial layer, and quality reports.
- `scripts/build_cdr_mapping_dashboard.py` — packages the spatial-layer artifacts with the dashboard files and builds the chemical search index and embedded data fallback.

The repository also contains previously generated workbook artifacts in `outputs/`. Their historical builder scripts are not part of the current `scripts/` directory.

## Open the dashboard

Double-click [`app/cdr_mapping_dashboard/index.html`](app/cdr_mapping_dashboard/index.html).

The dashboard loads its checked-in data assets directly from the same folder. `dashboard_data.js` provides an embedded fallback so the page can be opened from the filesystem without starting a server. The generated copy at [`outputs/cdr_mapping/index.html`](outputs/cdr_mapping/index.html) can be opened the same way.

The page loads Leaflet, MarkerCluster, and USGS basemap assets from external URLs. An internet connection is therefore needed for the map libraries and basemap; the dashboard's packaged data remains local.

The dashboard provides:

- Chemical and CAS-name search
- Facility and city filtering
- Activity filtering
- Facility markers and optional source-record points
- CBI-volume indicators without exposing numeric confidential values
- Public-coordinate precision labels and quality summaries

## Run the mapping pipeline

From the repository root, run the scripts in order:

```text
python scripts/build_cdr_mapping_data.py
python scripts/build_cdr_spatial_layer.py
python scripts/build_cdr_mapping_dashboard.py
```

The scripts write timestamped phase directories under `outputs/` and automatically discover the latest prior phase when an input directory is not supplied. Use explicit paths when a repeatable run needs fixed inputs and outputs:

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

Each build emits progress messages, a `build_manifest.json`, and quality findings. The dashboard build copies the HTML, JavaScript, CSS, GeoJSON, search index, metadata, summaries, and quality reports into its output directory.

## Data handling and limitations

- `source_row_id` preserves the link from normalized records back to the input CSV row.
- CBI values are represented as statuses or indicators rather than exposed numeric values.
- CBI location records are not inferred or plotted.
- The dashboard uses public source coordinates and labels their precision; it does not claim FRS-enriched facility matching.
- Numeric production, import, export, and use values are not displayed in the dashboard.
- Quality reports and unmapped-record extracts are retained for review instead of silently dropping problematic rows.

These outputs are transformed reporting data and exploration aids. They are not environmental risk assessments, exposure estimates, compliance determinations, or substitutes for source-document review.

## Requirements

- Python 3.10 or newer for the pipeline scripts
- A browser for the dashboard
- Internet access for the dashboard's external map libraries and basemap services

The current repository does not include a `requirements.txt`; the three mapping scripts are built around Python's standard library.

## Documentation

The [`Wiki/`](Wiki/) directory contains the detailed project notes, schema documentation, source records, script pages, and append-only change log. Start with [`Wiki/index.md`](Wiki/index.md).


Copyright © 2026 William Redmond. All rights reserved.
Permission is granted to view and review this source code and to run it solely for personal, educational, or internal evaluation purposes.
Commercial use, business use, publication, redistribution, sublicensing, modification, derivative works, and production deployment are prohibited without prior written permission.

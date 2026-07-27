# Repository Snapshot

- Canonical source path: `.`
- Source type: repository state
- Why it matters: captures the current project shape and points readers to the public entry point.
- Key points:
  - The repository now contains an executable CDR transformation pipeline rather than only a baseline scaffold.
  - `README.md` documents the three active mapping stages, current repository layout, direct dashboard launch, outputs, data-quality controls, and limitations.
  - The `scripts/` directory contains `build_cdr_mapping_data.py`, `build_cdr_spatial_layer.py`, and `build_cdr_mapping_dashboard.py`.
  - Generated artifacts include normalized CSV/SQLite layers, retained Excel workbooks, GeoJSON, dashboard assets, manifests, and quality reports.
  - The dashboard is file-based: open `app/cdr_mapping_dashboard/index.html` or `outputs/cdr_mapping/index.html` directly; no local server is required.
  - The Jupyter notebook remains available for CDR cleaning practice, ontology seed extraction, and starter normalized table work.
  - New work should preserve source-row provenance, CBI-safe handling, explicit data grain, progress logging, and the wiki governance pattern.
- Update triggers:
  - Any new repo files.
  - Any change to pipeline behavior, generated output families, root governance, environment setup, or data policy.
- Last reviewed date: 2026-07-27

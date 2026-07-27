# Repository Snapshot

- Canonical source path: `.`
- Source type: repository state
- Why it matters: captures the current project shape and points readers to the public entry point.
- Key points:
  - The repository now contains an executable CDR transformation pipeline rather than only a baseline scaffold.
  - `README.md` documents the end-to-end purpose, setup, pipeline stages, outputs, data-quality controls, and limitations.
  - The `scripts/` directory contains mapping data, spatial, dashboard, CAS, company, site, and workbook builders.
  - Generated artifacts include normalized CSV/SQLite layers, Excel workbooks, GeoJSON, dashboard assets, manifests, and quality reports.
  - The Jupyter notebook remains available for CDR cleaning practice, ontology seed extraction, and starter normalized table work.
  - New work should preserve source-row provenance, CBI-safe handling, explicit data grain, progress logging, and the wiki governance pattern.
- Update triggers:
  - Any new repo files.
  - Any change to pipeline behavior, generated output families, root governance, environment setup, or data policy.
- Last reviewed date: 2026-07-27

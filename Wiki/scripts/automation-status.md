# Automation Status

- Canonical source path: `.`
- Source type: script inventory
- Why it matters: documents the presence or absence of repo-local automation.
- Key points:
  - The current repository has three active mapping scripts: `scripts/build_cdr_mapping_data.py`, `scripts/build_cdr_spatial_layer.py`, and `scripts/build_cdr_mapping_dashboard.py`.
  - These scripts emit progress logging, timestamped output directories, build manifests, and quality reports.
  - The repository does not currently contain setup, lint, scraper, or workbook-builder scripts.
  - Previously generated workbook files are retained under `outputs/` as artifacts.
- Update triggers:
  - New script files.
  - Changes to build, setup, lint, or scraper automation.
- Last reviewed date: 2026-06-20

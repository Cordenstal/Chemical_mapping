# Repository README

- Canonical source path: `README.md`
- Source type: repository document
- Why it matters: provides the public entry point for the Chemical Mapping data-engineering and analytics project.
- Key points:
  - The repository contains three active CDR mapping scripts, a file-based dashboard under `app/cdr_mapping_dashboard/`, and retained generated artifacts under `outputs/`.
  - The dashboard is opened by double-clicking `app/cdr_mapping_dashboard/index.html`; no application server or local HTTP server is required.
  - The README documents the three sequential mapping stages, direct dashboard launch, generated output layout, CBI-safe handling, source-row provenance, and current analytical limitations.
  - Previously generated workbook artifacts remain in `outputs/`, but their historical builder scripts are not present in the current `scripts/` directory.
  - The wiki remains the detailed source of truth for individual scripts, schemas, outputs, and project history.
- Update triggers:
  - Repository scope changes.
  - Addition or removal of application code, scripts, or generated output families.
  - Changes to setup, pipeline behavior, data policy, or documented limitations.
- Last reviewed date: 2026-07-27

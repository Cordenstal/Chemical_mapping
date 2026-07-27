# Automation Status

- Canonical source path: `.`
- Source type: script inventory
- Why it matters: documents the presence or absence of repo-local automation.
- Key points:
  - The baseline includes one reusable bootstrap script in the skill itself.
  - Add script pages when setup, lint, or scraper automation is introduced.
  - Keep future script docs tied to one canonical file path each.
  - The portable ComfyUI root now also includes `install-comfyui-custom-node-deps.ps1` for recursive custom-node dependency installs.
  - The repo also includes `scripts/build_company_site_chemical_workbook.py` for generating a workbook with separate company, site, chemical, and filing-fact dataframes from the cleaned CDR source.
- Update triggers:
  - New script files.
  - Changes to build, setup, lint, or scraper automation.
- Last reviewed date: 2026-06-20

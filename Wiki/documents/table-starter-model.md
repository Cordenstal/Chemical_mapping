# Table Starter Model

- Canonical source path: `jupyter notebook 1.ipynb`
- Source type: notebook-derived table model
- Why it matters: this is the first pass at turning the wide CDR workbook into normalized entity and fact tables with stable keys and source-row provenance.
- Key points:
  - `company_table` uses `standardized_parent_company_name_normalized` as the company key.
  - `chemical_table` uses `chemical_id_w_o_dashes_normalized` as the chemical key.
  - `company_chemical_activity_fact` keeps code/label pairs together for validation.
  - `quantity_fact` keeps a raw quantity value plus a parsed numeric helper column.
  - `physical_form_fact` carries atomic physical-form rows forward from the source sheet.
  - Every derived table keeps `source_row_id` so the source workbook row is always traceable.
- Update triggers:
  - Any change to canonical company or chemical key selection.
  - Any change to the shape of the starter fact tables.
  - Any change to the volume, activity, or physical-form extraction rules.
- Last reviewed date: 2026-06-19

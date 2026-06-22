# Entity Ontology Seed

- Canonical source path: `jupyter notebook 1.ipynb`
- Source type: notebook-derived ontology seed design
- Why it matters: the notebook now extracts the ontology basis for this workbook by separating chemical entities and company entities, then extending those entities into starter entity and fact tables.
- Key points:
  - `chemical_entities` is built from chemical name and chemical identifier columns.
  - `company_entities` is built from standardized parent company name plus parent-company identifier columns.
  - The notebook logs each extraction step so a long or hung run is easy to diagnose.
  - The notebook now normalizes company names first, chemical IDs next, and preserves `source_row_id` on derived fact tables.
  - The company key is `standardized_parent_company_name_normalized`.
  - The chemical key is `chemical_id_w_o_dashes_normalized` from the undashed CAS number.
  - The resulting `company_table`, `chemical_table`, `company_chemical_activity_fact`, `quantity_fact`, and `physical_form_fact` frames provide the starter normalized model.
- Update triggers:
  - Any change to the entity extraction logic in the notebook.
  - Any change to the source columns used for chemical or company identity.
  - Any schema decision that changes the ontology seed structure.
- Last reviewed date: 2026-06-19

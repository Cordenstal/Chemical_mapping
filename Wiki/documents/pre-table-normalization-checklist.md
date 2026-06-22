# Pre-Table Normalization Checklist

- Canonical source path: `jupyter notebook 1.ipynb`
- Source type: notebook workflow checkpoint
- Why it matters: this checklist confirms the workbook is ready to become new tables without carrying avoidable encoding, keying, or provenance problems forward.
- Key points:
  - Confirms remaining encoding artifacts before downstream table creation.
  - Verifies the primary company key is the normalized standardized parent company name.
  - Verifies the primary chemical key is the undashed CAS number.
  - Keeps code/label pairs together until lookup validation is complete.
  - Treats sentinel values such as `CBI` and `NKRA` as explicit states that need a documented rule.
  - Requires `source_row_id` provenance on derived rows.
  - Confirms physical-form lists are atomic before table creation.
- Update triggers:
  - Any change to the notebook normalization flow.
  - Any change to keying, sentinel rules, or lookup validation.
  - Any change to the point where the workbook becomes table-ready.
- Last reviewed date: 2026-06-19

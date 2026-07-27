# CDR Mapping Phase 1 Data Layer

- Artifact pattern: `outputs/cdr_mapping_phase1_*/`
- Source: `data/raw data/2024 CDR Consumer and Commercial Use Information.csv`
- Builder: [CDR Mapping Phase 1 Importer](../scripts/build-cdr-mapping-data.md)

## Generated artifacts

- `cdr_records.csv`: all source columns with sensitive sentinel values blanked, plus normalized record fields.
- `chemicals.csv`: chemical identifier dimension.
- `facilities.csv`: preliminary facility dimension with public location fields and location status.
- `volume_facts.csv`: long-form volume facts with numeric values and value statuses.
- `field_status.csv`: field-level CBI, NKRA, and not-applicable status records.
- `cdr_mapping_phase1.sqlite`: queryable SQLite database containing the normalized tables.
- `quality_report.json`: machine-readable validation results.
- `quality_report.txt`: human-readable quality summary.
- `build_manifest.json`: source hash, output list, and CBI policy.

## Latest build

- Output: `outputs/cdr_mapping_phase1_20260724_112422/`
- Source rows: 64,023
- Source columns: 85
- Unique chemical keys: 8,553
- Public preliminary facility keys: 4,522
- Public source-coordinate records eligible for mapping: 53,025
- Records with CBI location fields: 10,993
- Records with CBI volume fields: 32,555
- Candidate duplicate groups requiring grain review: 32,480
- Candidate groups with conflicting numeric values: 852

## Important interpretation

The source provides an FRS field, but all 53,030 disclosed FRS values are represented in scientific notation in this CSV export. They are retained as disclosed text and are not treated as exact join keys in Phase 1. Preliminary facility keys therefore use public site identity fields. FRS matching belongs in a later enrichment and verification step.

The source-row grain is preserved. Candidate duplicate groups are reported but not collapsed because volume aggregation must first distinguish repeated reporting facts from distinct processing/use records.

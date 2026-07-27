# CDR Mapping Phase 1 Importer

- Script: `scripts/build_cdr_mapping_data.py`
- Source: `data/raw data/2024 CDR Consumer and Commercial Use Information.csv`
- Output: `outputs/cdr_mapping_phase1_*/`
- Purpose: Build the sanitized, queryable Phase 1 data layer for the CDR mapping system.

## Processing

- Reads the raw Windows-1252 CSV with all source columns preserved in the derived record export.
- Assigns `source_row_id` as the immutable source-record key.
- Normalizes chemical identifiers, chemical names, activity values, coordinates, facility keys, and FRS identifier text.
- Uses public site identity fields to build preliminary facility keys.
- Holds FRS values supplied in scientific notation out of exact joins until they are independently verified.
- Writes normalized CSV tables and a SQLite query database.
- Emits timestamped progress logging, a JSON manifest, and human-readable quality findings.

## CBI policy

- CBI, NKRA, and not-applicable sentinel values are blanked in derived value fields.
- `field_status.csv` records the source row, field, and status.
- CBI values are never used as numeric values, totals, map sizes, or coordinates.
- `has_cbi_*` flags identify records containing CBI values without exposing those values.
- `public_map_eligible` requires a complete valid source coordinate and no CBI location field.

## Validation

- Checks required headers and source row/column counts.
- Checks source-row uniqueness and malformed extra-column rows.
- Classifies coordinate completeness and validity.
- Profiles CBI field frequency, activity values, identifier types, and location states.
- Reports candidate duplicate chemical/facility/metric groups without deduplicating them automatically.
- Reports conflicting numeric values within candidate duplicate groups for later grain review.


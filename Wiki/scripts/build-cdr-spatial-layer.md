# CDR Mapping Phase 2 Spatial Layer

- Script: `scripts/build_cdr_spatial_layer.py`
- Input: latest `outputs/cdr_mapping_phase1_*/` directory
- Output: `outputs/cdr_mapping_phase2_*/`
- Purpose: Validate source coordinates and create CBI-safe spatial artifacts for the initial map.

## Processing

- Loads the sanitized Phase 1 records and facility dimension.
- Validates coordinate pairs, including an explicit rejection for `(0, 0)` null-island coordinates.
- Creates one GeoJSON point per eligible public CDR record.
- Creates one GeoJSON point per facility with at least one eligible public record.
- Produces facility-level location audits, unmapped-record audits, and state summaries.
- Builds a SQLite spatial index for local queries.
- Omits FRS identifiers from spatial properties because the source export represents disclosed FRS values in scientific notation and Phase 1 found no exact-join-eligible FRS values.

## CBI and volume policy

- Records with CBI location fields are excluded from GeoJSON.
- CBI locations are represented only through opaque record IDs, status flags, and rejection counts.
- CBI indicators are retained for facility and record properties where relevant.
- Numeric volume values are not included in Phase 2 spatial properties.
- Volume aggregation and marker sizing remain deferred until duplicate-grain review is complete.


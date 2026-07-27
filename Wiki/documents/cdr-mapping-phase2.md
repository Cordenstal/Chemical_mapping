# CDR Mapping Phase 2 Spatial Layer

- Artifact pattern: `outputs/cdr_mapping_phase2_*/`
- Source: canonical Phase 1 output
- Builder: [CDR Mapping Phase 2 Spatial Layer](../scripts/build-cdr-spatial-layer.md)

## Generated artifacts

- `public_facilities.geojson`: facility-level public points.
- `public_cdr_records.geojson`: source-record-level public points.
- `public_facilities.csv`: facility point properties.
- `public_cdr_records.csv`: record point properties.
- `location_audit.csv`: all Phase 1 facility rows with spatial eligibility and rejection status.
- `unmapped_records.csv`: non-map-eligible records with rejection reasons and CBI indicators.
- `state_summary.csv`: public facility, record, CBI-volume-indicator, and chemical counts by state.
- `cdr_mapping_phase2.sqlite`: local query index for spatial artifacts.
- `quality_report.json`: machine-readable spatial validation results.
- `quality_report.txt`: human-readable spatial findings.
- `build_manifest.json`: input lineage and spatial/CBI policy.

## Latest build

- Output: `outputs/cdr_mapping_phase2_20260724_112508/`
- Phase 1 facility rows reviewed: 15,515
- Public facility points: 4,279
- Public record points: 50,056
- Unmapped records: 13,967
- CBI-location records excluded: 10,993
- Null-island records excluded: 2,969
- Records missing coordinates: 5
- Facilities with coordinate variants: 3

## Important interpretation

The Phase 1 coordinate range checks alone were insufficient: 2,969 records had numeric `(0, 0)` coordinates. Phase 2 rejects these as `NULL_ISLAND_COORDINATE`; they must not appear on a map.

The spatial layer deliberately contains no numeric production, import, export, or on-site-use values. Phase 1 identified 852 candidate duplicate groups with conflicting numeric values, so volume aggregation and marker sizing remain deferred.

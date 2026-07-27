# CDR Mapping Phase 3 Dashboard Builder

## Purpose

`scripts/build_cdr_mapping_dashboard.py` packages the latest Phase 2 public spatial artifacts into a portable local dashboard. It creates a compact chemical search index and copies only the CBI-safe public layers and audit summaries needed by the app.

## Usage

```text
python scripts/build_cdr_mapping_dashboard.py
```

Optional arguments:

```text
python scripts/build_cdr_mapping_dashboard.py --phase2-dir outputs/cdr_mapping_phase2_YYYYMMDD_HHMMSS --output-dir outputs/cdr_mapping_phase3_custom
```

The builder logs input discovery, record indexing every 10,000 features, output creation, and the final dashboard path.

## Output

The checked-in dashboard package under `app/cdr_mapping_dashboard/` and the generated copy under `outputs/cdr_mapping/` contain:

- `index.html`, `app.js`, and `styles.css`: local dashboard application.
- `dashboard_data.js`: embedded direct-open fallback for browsers that block `fetch()` from `file://` pages.
- `chemical_index.json`: compact CAS/name search and public-count index.
- `dashboard_metadata.json`: source lineage, quality metadata, and CBI policy.
- Phase 2 public facility and record GeoJSON layers.
- State, unmapped-record, and quality-report artifacts.
- `build_manifest.json`: package lineage and policy.

Open the dashboard directly from the filesystem:

```text
app/cdr_mapping_dashboard/index.html
```

Double-click `index.html` in either dashboard directory. No local HTTP server is required because `dashboard_data.js` embeds the data needed for direct opening.

## CBI and volume policy

The dashboard exposes counts and a `CBI-volume indicator`, but it does not display numeric production, import, export, or use values. CBI location records are counted in summaries and remain unmapped. No inferred coordinates are created by this builder.

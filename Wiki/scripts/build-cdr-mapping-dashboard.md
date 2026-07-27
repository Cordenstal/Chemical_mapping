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

The generated `outputs/cdr_mapping_phase3_*/` package contains:

- `index.html`, `app.js`, and `styles.css`: local dashboard application.
- `dashboard_data.js`: embedded direct-open fallback for browsers that block `fetch()` from `file://` pages.
- `chemical_index.json`: compact CAS/name search and public-count index.
- `dashboard_metadata.json`: source lineage, quality metadata, and CBI policy.
- Phase 2 public facility and record GeoJSON layers.
- State, unmapped-record, and quality-report artifacts.
- `build_manifest.json`: package lineage and policy.

Serve the output directory with a local HTTP server for the preferred browser mode:

```text
python -m http.server 8000 --directory outputs/cdr_mapping_phase3_YYYYMMDD_HHMMSS
```

Then open `http://localhost:8000/`.

## CBI and volume policy

The dashboard exposes counts and a `CBI-volume indicator`, but it does not display numeric production, import, export, or use values. CBI location records are counted in summaries and remain unmapped. No inferred coordinates are created by this builder.

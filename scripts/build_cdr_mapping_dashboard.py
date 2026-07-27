from __future__ import annotations

import argparse
import csv
import json
import shutil
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUTPUTS = ROOT / "outputs"
APP_SOURCE = ROOT / "app" / "cdr_mapping_dashboard"


def log(message: str) -> None:
    print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] {message}", flush=True)


def latest_phase2_dir(root: Path) -> Path:
    candidates = sorted(path for path in root.glob("cdr_mapping_phase2_*") if path.is_dir())
    if not candidates:
        raise FileNotFoundError(f"No Phase 2 output directory found under {root}")
    return candidates[-1]


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def bool_value(value: object) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes"}


def copy_required_inputs(phase2_dir: Path, output_dir: Path) -> None:
    names = [
        "public_facilities.geojson",
        "public_cdr_records.geojson",
        "state_summary.csv",
        "unmapped_records.csv",
        "quality_report.json",
        "quality_report.txt",
    ]
    for name in names:
        source = phase2_dir / name
        if not source.exists():
            raise FileNotFoundError(f"Phase 2 output is missing required artifact: {source}")
        shutil.copy2(source, output_dir / name)


def build_chemical_index(phase2_dir: Path, output_dir: Path) -> dict[str, object]:
    log("Reading public record features for chemical and activity index")
    record_payload = json.loads((phase2_dir / "public_cdr_records.geojson").read_text(encoding="utf-8"))
    unmapped_rows = read_rows(phase2_dir / "unmapped_records.csv")

    records_by_chemical: dict[str, dict[str, object]] = {}
    facility_sets: defaultdict[str, set[str]] = defaultdict(set)
    state_sets: defaultdict[str, set[str]] = defaultdict(set)
    activity_sets: defaultdict[str, set[str]] = defaultdict(set)
    cbi_volume_counts: Counter[str] = Counter()

    for number, feature in enumerate(record_payload.get("features", []), start=1):
        properties = feature.get("properties", {})
        chemical_key = str(properties.get("chemical_key", "")).strip()
        if not chemical_key:
            continue
        chemical = records_by_chemical.setdefault(
            chemical_key,
            {
                "chemical_key": chemical_key,
                "chemical_name": properties.get("chemical_name", "") or "(name unavailable)",
                "public_record_count": 0,
                "public_facility_count": 0,
                "public_state_count": 0,
                "public_has_cbi_volume_record_count": 0,
                "withheld_location_record_count": 0,
                "activities": [],
                "states": [],
            },
        )
        chemical["public_record_count"] += 1
        facility_sets[chemical_key].add(str(properties.get("facility_id", "")))
        state = str(properties.get("site_state", "")).strip()
        if state:
            state_sets[chemical_key].add(state)
        activity = str(properties.get("activity", "")).strip()
        if activity:
            activity_sets[chemical_key].add(activity)
        if bool_value(properties.get("has_cbi_volume")):
            cbi_volume_counts[chemical_key] += 1
        if number % 10000 == 0:
            log(f"Indexed {number:,} public record features")

    withheld_location_counts: Counter[str] = Counter()
    for row in unmapped_rows:
        chemical_key = row.get("chemical_key", "").strip()
        if chemical_key and bool_value(row.get("has_cbi_location")):
            withheld_location_counts[chemical_key] += 1

    for chemical_key, chemical in records_by_chemical.items():
        chemical["public_facility_count"] = len(facility_sets[chemical_key])
        chemical["public_state_count"] = len(state_sets[chemical_key])
        chemical["public_has_cbi_volume_record_count"] = cbi_volume_counts[chemical_key]
        chemical["withheld_location_record_count"] = withheld_location_counts[chemical_key]
        chemical["activities"] = sorted(activity_sets[chemical_key])
        chemical["states"] = sorted(state_sets[chemical_key])

    index = {
        "generated_at": datetime.now().isoformat(),
        "chemical_count": len(records_by_chemical),
        "chemicals": sorted(records_by_chemical.values(), key=lambda row: (str(row["chemical_name"]).lower(), str(row["chemical_key"]))),
    }
    (output_dir / "chemical_index.json").write_text(json.dumps(index, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    return index


def build_dashboard_metadata(phase2_dir: Path, output_dir: Path, chemical_index: dict[str, object]) -> dict[str, object]:
    quality = json.loads((phase2_dir / "quality_report.json").read_text(encoding="utf-8"))
    unmapped = read_rows(phase2_dir / "unmapped_records.csv")
    metadata = {
        "phase": 3,
        "phase2_input": str(phase2_dir),
        "phase2_quality": quality,
        "chemical_count_in_public_index": chemical_index["chemical_count"],
        "unmapped_record_count": len(unmapped),
        "cbi_location_record_count": sum(bool_value(row.get("has_cbi_location")) for row in unmapped),
        "cbi_volume_indicator_record_count": sum(bool_value(row.get("has_cbi_volume")) for row in unmapped),
        "policy": {
            "numeric_volume_values_displayed": False,
            "cbi_values_displayed": False,
            "cbi_location_records_mapped": False,
            "cbi_indicators_displayed": True,
            "source_coordinate_precision_labeled": True,
        },
        "notes": [
            "The dashboard uses public Phase 2 source-coordinate points only.",
            "CBI location records are summarized by count and never assigned inferred coordinates.",
            "Numeric production, import, export, and use values are not present in the dashboard payload.",
            "Facility markers aggregate public records; record markers preserve source-record detail.",
        ],
    }
    (output_dir / "dashboard_metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    return metadata


def write_embedded_data(output_dir: Path, metadata: dict[str, object], chemical_index: dict[str, object]) -> None:
    """Write a direct-open fallback so file:// launches do not depend on fetch/CORS."""
    log("Creating direct-open embedded data payload")
    payload = {
        "facilities": json.loads((output_dir / "public_facilities.geojson").read_text(encoding="utf-8")),
        "records": json.loads((output_dir / "public_cdr_records.geojson").read_text(encoding="utf-8")),
        "index": chemical_index,
        "metadata": metadata,
    }
    embedded = "window.CDR_DASHBOARD_DATA = " + json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + ";\n"
    (output_dir / "dashboard_data.js").write_text(embedded, encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the Phase 3 CDR mapping dashboard package.")
    parser.add_argument("--phase2-dir", type=Path, default=None)
    parser.add_argument("--output-dir", type=Path, default=None)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    phase2_dir = (args.phase2_dir or latest_phase2_dir(OUTPUTS)).resolve()
    output_dir = (args.output_dir or OUTPUTS / f"cdr_mapping_phase3_{datetime.now():%Y%m%d_%H%M%S}").resolve()
    if output_dir.exists():
        raise FileExistsError(f"Output directory already exists: {output_dir}")
    output_dir.mkdir(parents=True)

    log(f"Phase 2 input: {phase2_dir}")
    log(f"Dashboard output: {output_dir}")
    copy_required_inputs(phase2_dir, output_dir)
    chemical_index = build_chemical_index(phase2_dir, output_dir)
    metadata = build_dashboard_metadata(phase2_dir, output_dir, chemical_index)
    write_embedded_data(output_dir, metadata, chemical_index)

    for source_name in ["index.html", "app.js", "styles.css"]:
        source = APP_SOURCE / source_name
        if not source.exists():
            raise FileNotFoundError(f"Dashboard source file is missing: {source}")
        shutil.copy2(source, output_dir / source_name)

    manifest = {
        "phase": 3,
        "source_phase2_dir": str(phase2_dir),
        "output_dir": str(output_dir),
        "created_at": datetime.now().isoformat(),
        "artifacts": [
            "index.html",
            "app.js",
            "styles.css",
            "chemical_index.json",
            "dashboard_metadata.json",
            "dashboard_data.js",
            "public_facilities.geojson",
            "public_cdr_records.geojson",
            "state_summary.csv",
            "unmapped_records.csv",
            "quality_report.json",
            "quality_report.txt",
        ],
        "policy": {
            "numeric_volume_values_displayed": False,
            "cbi_values_displayed": False,
            "cbi_location_records_mapped": False,
            "cbi_indicators_displayed": True,
        },
    }
    (output_dir / "build_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    log(f"Indexed {chemical_index['chemical_count']:,} chemicals")
    log("Phase 3 dashboard package complete")
    log(f"Open with a local web server: {output_dir / 'index.html'}")


if __name__ == "__main__":
    main()

from __future__ import annotations

import argparse
import csv
import json
import sqlite3
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PHASE1_ROOT = ROOT / "outputs"


def log(message: str) -> None:
    print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] {message}", flush=True)


def as_bool(value: object) -> bool:
    return str(value).strip() in {"1", "true", "True", "yes", "Yes"}


def as_float(value: object) -> float | None:
    try:
        return float(str(value).strip())
    except (TypeError, ValueError):
        return None


def coordinate_check(latitude: object, longitude: object) -> tuple[bool, str, float | None, float | None]:
    lat = as_float(latitude)
    lon = as_float(longitude)
    if lat is None or lon is None:
        return False, "MISSING_COORDINATE", lat, lon
    if lat == 0 and lon == 0:
        return False, "NULL_ISLAND_COORDINATE", lat, lon
    if not -90 <= lat <= 90 or not -180 <= lon <= 180:
        return False, "OUT_OF_RANGE_COORDINATE", lat, lon
    return True, "VALID_SOURCE_COORDINATE", lat, lon


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def latest_phase1_dir(root: Path) -> Path:
    candidates = sorted(root.glob("cdr_mapping_phase1_*"))
    candidates = [path for path in candidates if path.is_dir()]
    if not candidates:
        raise FileNotFoundError(f"No Phase 1 output directory found under {root}")
    return candidates[-1]


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, object]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def feature(properties: dict[str, object], longitude: float, latitude: float) -> dict[str, object]:
    return {
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": [longitude, latitude]},
        "properties": properties,
    }


def write_geojson(path: Path, features: list[dict[str, object]]) -> None:
    payload = {"type": "FeatureCollection", "features": features}
    path.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")


def build_sqlite(path: Path, facilities: list[dict[str, object]], records: list[dict[str, object]], unmapped: list[dict[str, object]], states: list[dict[str, object]]) -> None:
    log("Building Phase 2 SQLite spatial index")
    connection = sqlite3.connect(path)
    try:
        connection.executescript(
            """
            PRAGMA journal_mode = WAL;
            CREATE TABLE public_facilities (
                facility_id TEXT PRIMARY KEY,
                site_name TEXT,
                site_city TEXT,
                site_state TEXT,
                latitude REAL,
                longitude REAL,
                location_precision TEXT,
                source_record_count INTEGER,
                chemical_count INTEGER,
                activity_count INTEGER,
                has_cbi_volume INTEGER,
                coordinate_variant_count INTEGER
            );
            CREATE TABLE public_cdr_records (
                source_row_id TEXT,
                record_id TEXT PRIMARY KEY,
                chemical_key TEXT,
                chemical_name TEXT,
                facility_id TEXT,
                site_name TEXT,
                site_city TEXT,
                site_state TEXT,
                activity TEXT,
                latitude REAL,
                longitude REAL,
                has_cbi_volume INTEGER,
                location_precision TEXT
            );
            CREATE TABLE unmapped_records (
                source_row_id TEXT,
                record_id TEXT PRIMARY KEY,
                chemical_key TEXT,
                facility_id TEXT,
                location_status TEXT,
                coordinate_status TEXT,
                rejection_reason TEXT,
                has_cbi_location INTEGER,
                has_cbi_volume INTEGER
            );
            CREATE TABLE state_summary (
                state TEXT PRIMARY KEY,
                public_facility_count INTEGER,
                public_record_count INTEGER,
                record_count_with_cbi_volume INTEGER,
                unique_chemical_count INTEGER
            );
            CREATE INDEX idx_spatial_records_chemical ON public_cdr_records (chemical_key);
            CREATE INDEX idx_spatial_records_facility ON public_cdr_records (facility_id);
            CREATE INDEX idx_unmapped_reason ON unmapped_records (rejection_reason);
            """
        )
        connection.executemany(
            "INSERT INTO public_facilities VALUES (:facility_id, :site_name, :site_city, :site_state, :latitude, :longitude, :location_precision, :source_record_count, :chemical_count, :activity_count, :has_cbi_volume, :coordinate_variant_count)",
            facilities,
        )
        connection.executemany(
            "INSERT INTO public_cdr_records VALUES (:source_row_id, :record_id, :chemical_key, :chemical_name, :facility_id, :site_name, :site_city, :site_state, :activity, :latitude, :longitude, :has_cbi_volume, :location_precision)",
            records,
        )
        connection.executemany(
            "INSERT INTO unmapped_records VALUES (:source_row_id, :record_id, :chemical_key, :facility_id, :location_status, :coordinate_status, :rejection_reason, :has_cbi_location, :has_cbi_volume)",
            unmapped,
        )
        connection.executemany(
            "INSERT INTO state_summary VALUES (:state, :public_facility_count, :public_record_count, :record_count_with_cbi_volume, :unique_chemical_count)",
            states,
        )
        connection.commit()
    finally:
        connection.close()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build Phase 2 CDR spatial artifacts from Phase 1 outputs.")
    parser.add_argument("--phase1-dir", type=Path, default=None)
    parser.add_argument("--output-dir", type=Path, default=None)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    phase1_dir = (args.phase1_dir or latest_phase1_dir(DEFAULT_PHASE1_ROOT)).resolve()
    required = [phase1_dir / "cdr_records.csv", phase1_dir / "facilities.csv", phase1_dir / "quality_report.json"]
    missing = [str(path) for path in required if not path.exists()]
    if missing:
        raise FileNotFoundError(f"Phase 1 output is missing required artifacts: {missing}")

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = (args.output_dir or ROOT / "outputs" / f"cdr_mapping_phase2_{timestamp}").resolve()
    output_dir.mkdir(parents=True, exist_ok=False)
    log(f"Phase 1 input: {phase1_dir}")
    log(f"Output: {output_dir}")

    phase1_quality = json.loads((phase1_dir / "quality_report.json").read_text(encoding="utf-8"))
    facilities = {row["facility_id"]: row for row in read_rows(phase1_dir / "facilities.csv")}
    log(f"Loaded {len(facilities):,} Phase 1 facility rows")

    public_record_rows: list[dict[str, object]] = []
    public_record_features: list[dict[str, object]] = []
    unmapped_rows: list[dict[str, object]] = []
    facility_points: dict[str, set[tuple[float, float]]] = defaultdict(set)
    facility_record_counts: Counter[str] = Counter()
    facility_chemical_keys: dict[str, set[str]] = defaultdict(set)
    facility_activities: dict[str, set[str]] = defaultdict(set)
    facility_cbi_volume: Counter[str] = Counter()
    state_records: Counter[str] = Counter()
    state_cbi_volume: Counter[str] = Counter()
    state_chemicals: dict[str, set[str]] = defaultdict(set)
    state_facilities: dict[str, set[str]] = defaultdict(set)
    rejection_counts: Counter[str] = Counter()
    coordinate_variant_facilities: set[str] = set()
    null_island_records = 0
    malformed_record_ids = 0

    log("Validating record coordinates and building public record points")
    with (phase1_dir / "cdr_records.csv").open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for row_number, row in enumerate(reader, start=1):
            record_id = row.get("record_id", "")
            source_row_id_text = row.get("source_row_id", "")
            try:
                source_row_id: int | str = int(source_row_id_text)
            except (TypeError, ValueError):
                source_row_id = source_row_id_text
            if not record_id or not source_row_id_text:
                malformed_record_ids += 1
            lat_ok, coordinate_state, latitude, longitude = coordinate_check(row.get("SITE LATITUDE", ""), row.get("SITE LONGITUDE", ""))
            requested_map = as_bool(row.get("public_map_eligible", "0"))
            cbi_location = as_bool(row.get("has_cbi_location", "0"))
            if coordinate_state == "NULL_ISLAND_COORDINATE":
                null_island_records += 1
            eligible = requested_map and not cbi_location and lat_ok and row.get("coordinate_status") == "SOURCE_COORDINATE"
            if not eligible:
                if cbi_location or row.get("location_status") == "CBI":
                    reason = "CBI_LOCATION_WITHHELD"
                elif coordinate_state == "NULL_ISLAND_COORDINATE":
                    reason = coordinate_state
                elif coordinate_state != "VALID_SOURCE_COORDINATE":
                    reason = coordinate_state
                elif row.get("location_status") == "ADDRESS_ONLY":
                    reason = "ADDRESS_REQUIRES_GEOCODING"
                else:
                    reason = "SOURCE_RECORD_NOT_MAP_ELIGIBLE"
                rejection_counts[reason] += 1
                unmapped_rows.append(
                    {
                        "source_row_id": source_row_id,
                        "record_id": record_id,
                        "chemical_key": row.get("chemical_key", ""),
                        "facility_id": row.get("facility_id", ""),
                        "location_status": row.get("location_status", ""),
                        "coordinate_status": row.get("coordinate_status", ""),
                        "rejection_reason": reason,
                        "has_cbi_location": int(cbi_location),
                        "has_cbi_volume": int(as_bool(row.get("has_cbi_volume", "0"))),
                    }
                )
            else:
                facility_id = row.get("facility_id", "")
                state = row.get("SITE STATE", "") or "UNKNOWN"
                activity = row.get("ACTIVITY", "") or row.get("activity_normalized", "")
                point_row = {
                    "source_row_id": source_row_id,
                    "record_id": record_id,
                    "chemical_key": row.get("chemical_key", ""),
                    "chemical_name": row.get("CHEMICAL NAME", ""),
                    "facility_id": facility_id,
                    "site_name": row.get("SITE NAME", ""),
                    "site_city": row.get("SITE CITY", ""),
                    "site_state": state,
                    "activity": activity,
                    "latitude": latitude,
                    "longitude": longitude,
                    "has_cbi_volume": int(as_bool(row.get("has_cbi_volume", "0"))),
                    "location_precision": "SOURCE_COORDINATE",
                }
                public_record_rows.append(point_row)
                public_record_features.append(
                    feature(
                        {
                            "source_row_id": source_row_id,
                            "record_id": record_id,
                            "chemical_key": row.get("chemical_key", ""),
                            "chemical_name": row.get("CHEMICAL NAME", ""),
                            "facility_id": facility_id,
                            "site_name": row.get("SITE NAME", ""),
                            "site_city": row.get("SITE CITY", ""),
                            "site_state": state,
                            "activity": activity,
                            "has_cbi_volume": int(as_bool(row.get("has_cbi_volume", "0"))),
                            "location_precision": "SOURCE_COORDINATE",
                        },
                        longitude,
                        latitude,
                    )
                )
                facility_points[facility_id].add((latitude, longitude))
                facility_record_counts[facility_id] += 1
                facility_chemical_keys[facility_id].add(row.get("chemical_key", ""))
                if activity:
                    facility_activities[facility_id].add(activity)
                facility_cbi_volume[facility_id] += int(as_bool(row.get("has_cbi_volume", "0")))
                state_records[state] += 1
                state_facilities[state].add(facility_id)
                state_chemicals[state].add(row.get("chemical_key", ""))
                state_cbi_volume[state] += int(as_bool(row.get("has_cbi_volume", "0")))

            if row_number % 10000 == 0:
                log(f"Validated {row_number:,} records")

    for facility_id, points in facility_points.items():
        source_variant_count = int(facilities.get(facility_id, {}).get("coordinate_variant_count", "0") or 0)
        if len(points) > 1 or source_variant_count > 1:
            coordinate_variant_facilities.add(facility_id)

    public_facility_rows: list[dict[str, object]] = []
    public_facility_features: list[dict[str, object]] = []
    location_audit_rows: list[dict[str, object]] = []
    for facility_id, source_facility in facilities.items():
        points = facility_points.get(facility_id, set())
        map_eligible = bool(points)
        if map_eligible:
            latitude, longitude = sorted(points)[0]
            location_precision = "SOURCE_COORDINATE"
            rejection_reason = ""
            public_facility_row = {
                "facility_id": facility_id,
                "site_name": source_facility.get("site_name", ""),
                "site_city": source_facility.get("site_city", ""),
                "site_state": source_facility.get("site_state", "") or "UNKNOWN",
                "latitude": latitude,
                "longitude": longitude,
                "location_precision": location_precision,
                "source_record_count": facility_record_counts[facility_id],
                "chemical_count": len(facility_chemical_keys[facility_id]),
                "activity_count": len(facility_activities[facility_id]),
                "has_cbi_volume": int(facility_cbi_volume[facility_id] > 0),
                "coordinate_variant_count": max(len(points), int(source_facility.get("coordinate_variant_count", "0") or 0)),
            }
            public_facility_rows.append(public_facility_row)
            public_facility_features.append(
                feature(
                    {
                        "facility_id": facility_id,
                        "site_name": source_facility.get("site_name", ""),
                        "site_city": source_facility.get("site_city", ""),
                        "site_state": source_facility.get("site_state", "") or "UNKNOWN",
                        "location_precision": location_precision,
                        "source_record_count": facility_record_counts[facility_id],
                        "chemical_count": len(facility_chemical_keys[facility_id]),
                        "activity_count": len(facility_activities[facility_id]),
                        "has_cbi_volume": int(facility_cbi_volume[facility_id] > 0),
                        "coordinate_variant_count": public_facility_row["coordinate_variant_count"],
                    },
                    longitude,
                    latitude,
                )
            )
        else:
            location_status = source_facility.get("location_status", "UNAVAILABLE")
            if location_status == "CBI":
                rejection_reason = "CBI_LOCATION_WITHHELD"
            elif location_status == "ADDRESS_ONLY":
                rejection_reason = "ADDRESS_REQUIRES_GEOCODING"
            elif location_status == "SOURCE_COORDINATE":
                rejection_reason = "NO_VALID_SOURCE_COORDINATE"
            else:
                rejection_reason = "LOCATION_UNAVAILABLE"
            location_precision = "CBI" if location_status == "CBI" else location_status
        location_audit_rows.append(
            {
                **source_facility,
                "map_eligible": int(map_eligible),
                "spatial_location_precision": location_precision,
                "spatial_rejection_reason": rejection_reason,
                "spatial_coordinate_variant_count": len(points),
            }
        )

    state_rows = []
    for state in sorted(set(state_records) | set(state_facilities) | set(state_chemicals)):
        state_rows.append(
            {
                "state": state,
                "public_facility_count": len(state_facilities[state]),
                "public_record_count": state_records[state],
                "record_count_with_cbi_volume": state_cbi_volume[state],
                "unique_chemical_count": len(state_chemicals[state]),
            }
        )

    log("Writing GeoJSON, CSV, SQLite, and validation reports")
    write_geojson(output_dir / "public_facilities.geojson", public_facility_features)
    write_geojson(output_dir / "public_cdr_records.geojson", public_record_features)
    write_csv(output_dir / "public_facilities.csv", list(public_facility_rows[0].keys()) if public_facility_rows else ["facility_id"], public_facility_rows)
    write_csv(output_dir / "public_cdr_records.csv", list(public_record_rows[0].keys()) if public_record_rows else ["source_row_id"], public_record_rows)
    write_csv(output_dir / "location_audit.csv", list(location_audit_rows[0].keys()) if location_audit_rows else ["facility_id"], location_audit_rows)
    write_csv(output_dir / "unmapped_records.csv", list(unmapped_rows[0].keys()) if unmapped_rows else ["source_row_id"], unmapped_rows)
    write_csv(output_dir / "state_summary.csv", list(state_rows[0].keys()) if state_rows else ["state"], state_rows)
    build_sqlite(output_dir / "cdr_mapping_phase2.sqlite", public_facility_rows, public_record_rows, unmapped_rows, state_rows)

    quality_report = {
        "phase": 2,
        "phase1_input": str(phase1_dir),
        "phase1_source_row_count": phase1_quality.get("source_row_count"),
        "phase1_source_sha256": phase1_quality.get("source_sha256"),
        "facility_input_count": len(facilities),
        "public_facility_count": len(public_facility_rows),
        "public_record_point_count": len(public_record_rows),
        "unmapped_record_count": len(unmapped_rows),
        "public_facility_feature_count": len(public_facility_features),
        "public_record_feature_count": len(public_record_features),
        "rejection_counts": dict(rejection_counts),
        "null_island_records": null_island_records,
        "malformed_record_ids": malformed_record_ids,
        "coordinate_variant_facility_count": len(coordinate_variant_facilities),
        "state_count": len(state_rows),
        "volume_aggregation_deferred": True,
        "phase1_candidate_conflicting_volume_groups": phase1_quality.get("conflicting_candidate_duplicate_groups"),
        "cbi_policy": {
            "cbi_location_records_are_mapped": False,
            "cbi_values_are_in_spatial_properties": False,
            "cbi_volume_values_are_in_spatial_properties": False,
            "cbi_volume_indicator_is_exposed": True,
        },
        "notes": [
            "GeoJSON contains public source-coordinate points only.",
            "CBI location records are represented in unmapped_records.csv and rejection counts, not as points.",
            "Numeric volume values are intentionally absent from Phase 2 spatial properties until Phase 1 grain conflicts are resolved.",
            "FRS IDs are omitted from spatial properties because the Phase 1 CSV represents disclosed FRS values in scientific notation and none are exact-join eligible.",
        ],
    }
    (output_dir / "quality_report.json").write_text(json.dumps(quality_report, indent=2), encoding="utf-8")

    report_lines = [
        "CDR mapping Phase 2 spatial-layer quality report",
        "=================================================",
        f"Phase 1 facility rows: {len(facilities):,}",
        f"Public facility points: {len(public_facility_rows):,}",
        f"Public record points: {len(public_record_rows):,}",
        f"Unmapped records: {len(unmapped_rows):,}",
        f"Coordinate-variant facilities: {len(coordinate_variant_facilities):,}",
        f"Null-island records rejected: {null_island_records:,}",
        f"Conflicting Phase 1 volume groups not visualized: {quality_report['phase1_candidate_conflicting_volume_groups']:,}",
        "",
        "Spatial rejection counts:",
    ]
    report_lines.extend(f"  {key}: {value:,}" for key, value in sorted(rejection_counts.items()))
    report_lines.extend(
        [
            "",
            "Interpretation:",
            "  Public GeoJSON points contain no numeric volume values and no CBI values.",
            "  CBI location records remain auditable through opaque record IDs and status flags only.",
            "  FRS values are not used for exact joins in this spatial build.",
            "  Volume symbology is deferred until duplicate-grain review is complete.",
        ]
    )
    (output_dir / "quality_report.txt").write_text("\n".join(report_lines) + "\n", encoding="utf-8")

    manifest = {
        "phase": 2,
        "phase1_input": str(phase1_dir),
        "phase1_source_sha256": phase1_quality.get("source_sha256"),
        "output_dir": str(output_dir),
        "created_at": datetime.now().isoformat(),
        "artifacts": [
            "public_facilities.geojson",
            "public_cdr_records.geojson",
            "public_facilities.csv",
            "public_cdr_records.csv",
            "location_audit.csv",
            "unmapped_records.csv",
            "state_summary.csv",
            "cdr_mapping_phase2.sqlite",
            "quality_report.json",
            "quality_report.txt",
        ],
        "policy": {
            "cbi_location_records_mapped": False,
            "cbi_values_reported": False,
            "cbi_indicators_preserved": True,
            "numeric_volume_values_reported": False,
            "volume_aggregation_deferred": True,
            "frs_exact_join_used": False,
        },
    }
    (output_dir / "build_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    log("Phase 2 complete")
    log(f"Quality report: {output_dir / 'quality_report.txt'}")
    log(f"Facility GeoJSON: {output_dir / 'public_facilities.geojson'}")
    log(f"Record GeoJSON: {output_dir / 'public_cdr_records.geojson'}")


if __name__ == "__main__":
    main()

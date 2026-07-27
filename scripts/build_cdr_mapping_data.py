from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sqlite3
from collections import Counter, defaultdict
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE = ROOT / "data" / "raw data" / "2024 CDR Consumer and Commercial Use Information.csv"
DEFAULT_ENCODING = "cp1252"

CBI = "CBI"
NKRA = "NKRA"
NOT_APPLICABLE = "NOT_APPLICABLE"
MISSING = "MISSING"
DISCLOSED = "DISCLOSED"

LOCATION_FIELDS = [
    "SITE NAME",
    "SITE ADDRESS LINE1",
    "SITE ADDRESS LINE2",
    "SITE CITY",
    "SITE COUNTY / PARISH",
    "SITE STATE",
    "SITE POSTAL CODE",
    "SITE LATITUDE",
    "SITE LONGITUDE",
    "EPA FACILITY REGISTRY ID",
]

VOLUME_FIELDS = [
    ("2023 DOMESTIC PV", 2023, "domestic_production"),
    ("2023 IMPORT PV", 2023, "import"),
    ("2023 PV", 2023, "total_production"),
    ("2023 V EXPORTED", 2023, "export"),
    ("2023 V USED ON-SITE", 2023, "used_on_site"),
    ("2022 PV", 2022, "total_production"),
    ("2021 PV", 2021, "total_production"),
    ("2020 PV", 2020, "total_production"),
]

DERIVED_RECORD_FIELDS = [
    "record_id",
    "chemical_key",
    "facility_id",
    "chemical_identifier_normalized",
    "chemical_identifier_type",
    "chemical_identifier_status",
    "chemical_name_normalized",
    "activity_normalized",
    "frs_id_normalized",
    "frs_id_join_eligible",
    "coordinate_status",
    "location_status",
    "has_cbi_any",
    "has_cbi_volume",
    "has_cbi_location",
    "public_map_eligible",
]


def log(message: str) -> None:
    print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] {message}", flush=True)


def clean_text(value: object) -> str:
    if value is None:
        return ""
    return " ".join(str(value).replace("\u00a0", " ").split())


def classify_value(value: object) -> tuple[str, str]:
    """Return a safe display value and a state without exposing sentinel values."""
    value_text = clean_text(value)
    upper = value_text.upper()
    if not value_text:
        return "", MISSING
    if upper == "CBI":
        return "", CBI
    if upper in {"NKRA", "NOT KNOWN OR REASONABLY ASCERTAINABLE"}:
        return "", NKRA
    if upper in {"N/A", "NA", "NOT APPLICABLE"}:
        return "", NOT_APPLICABLE
    return value_text, DISCLOSED


def normalize_key(value: object) -> str:
    value_text = clean_text(value).upper()
    value_text = re.sub(r"[^A-Z0-9]+", " ", value_text)
    return " ".join(value_text.split())


def normalize_identifier(row: dict[str, str], statuses: dict[str, str]) -> tuple[str, str, str]:
    identifier_type = row.get("CHEMICAL ID TYPE", "")
    identifier_type_status = statuses.get("CHEMICAL ID TYPE", MISSING)
    type_value = identifier_type if identifier_type_status == DISCLOSED else ""
    raw_identifier = row.get("CHEMICAL ID W/O DASHES", "") or row.get("CHEMICAL ID", "")
    raw_status = statuses.get("CHEMICAL ID W/O DASHES", MISSING)
    if raw_status in {MISSING, NOT_APPLICABLE}:
        raw_status = statuses.get("CHEMICAL ID", raw_status)
        raw_identifier = row.get("CHEMICAL ID", "")
    if raw_status != DISCLOSED:
        return "", type_value, raw_status
    if type_value.upper() == "CASRN":
        normalized = re.sub(r"[^0-9]", "", raw_identifier)
    else:
        normalized = re.sub(r"\s+", "", raw_identifier.upper())
    return normalized, type_value, DISCLOSED if normalized else MISSING


def normalize_frs_id(value: str) -> str:
    """Keep FRS identifiers as text, including values read from scientific notation."""
    value_text = clean_text(value)
    if not value_text:
        return ""
    try:
        if "e" in value_text.lower():
            decimal_value = Decimal(value_text)
            if decimal_value == decimal_value.to_integral_value():
                return str(decimal_value.to_integral_value())
        if re.fullmatch(r"[0-9]+(?:\.0+)?", value_text):
            return value_text.split(".", 1)[0]
    except InvalidOperation:
        return ""
    return value_text


def parse_number(value: str, status: str) -> tuple[str, str]:
    if status != DISCLOSED:
        return "", status
    normalized = value.replace(",", "").strip()
    if not normalized:
        return "", MISSING
    try:
        number = Decimal(normalized)
    except InvalidOperation:
        if any(token in normalized for token in ("<", ">", "–", "-", "to", "TO")):
            return "", "RANGE"
        return "", "DISCLOSED_TEXT"
    if not number.is_finite():
        return "", "INVALID"
    return format(number, "f").rstrip("0").rstrip(".") or "0", "DISCLOSED_NUMERIC"


def valid_coordinate(value: str) -> bool:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return False
    return -180 <= number <= 180


def coordinate_status(row: dict[str, str], statuses: dict[str, str], site_has_cbi: bool) -> tuple[str, str, str]:
    lat, lat_status = row.get("SITE LATITUDE", ""), statuses.get("SITE LATITUDE", MISSING)
    lon, lon_status = row.get("SITE LONGITUDE", ""), statuses.get("SITE LONGITUDE", MISSING)
    if lat_status == CBI or lon_status == CBI or site_has_cbi:
        return "", "", "CBI"
    if lat_status == DISCLOSED and lon_status == DISCLOSED:
        try:
            latitude = float(lat)
            longitude = float(lon)
        except ValueError:
            return "", "", "INVALID"
        if -90 <= latitude <= 90 and -180 <= longitude <= 180:
            return f"{latitude:.8f}".rstrip("0").rstrip("."), f"{longitude:.8f}".rstrip("0").rstrip("."), "SOURCE_COORDINATE"
        return "", "", "INVALID"
    if lat_status == DISCLOSED or lon_status == DISCLOSED:
        return "", "", "INCOMPLETE"
    return "", "", "MISSING"


def sha_key(parts: list[str]) -> str:
    payload = "|".join(parts).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()[:24]


def build_facility_id(row: dict[str, str], statuses: dict[str, str], frs_id: str, frs_id_source: str, source_row_id: int) -> str:
    site_has_cbi = any(statuses.get(field) == CBI for field in LOCATION_FIELDS)
    if site_has_cbi:
        return f"REDACTED_RECORD:{source_row_id}"
    public_parts = [
        normalize_key(row.get("SITE NAME", "")),
        normalize_key(row.get("SITE ADDRESS LINE1", "")),
        normalize_key(row.get("SITE ADDRESS LINE2", "")),
        normalize_key(row.get("SITE CITY", "")),
        normalize_key(row.get("SITE STATE", "")),
        normalize_key(row.get("SITE POSTAL CODE", "")),
    ]
    if any(public_parts):
        return f"SRC:{sha_key(public_parts)}"
    if frs_id and "e" not in frs_id_source.lower():
        return f"FRS:{frs_id}"
    return f"RECORD:{source_row_id}"


def location_status(row: dict[str, str], statuses: dict[str, str], coordinate_state: str, frs_id: str) -> str:
    if any(statuses.get(field) == CBI for field in LOCATION_FIELDS):
        return "CBI"
    if coordinate_state == "SOURCE_COORDINATE":
        return coordinate_state
    if coordinate_state in {"INVALID", "INCOMPLETE"}:
        return coordinate_state
    if row.get("SITE ADDRESS LINE1") and row.get("SITE CITY") and row.get("SITE STATE"):
        return "ADDRESS_ONLY"
    if row.get("SITE CITY") and row.get("SITE STATE"):
        return "CITY_STATE_ONLY"
    if frs_id:
        return "FRS_ID_ONLY"
    return "UNAVAILABLE"


def safe_sql_identifier(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, object]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def create_sqlite(path: Path, records: list[dict[str, object]], chemicals: list[dict[str, object]], facilities: list[dict[str, object]], volumes: list[dict[str, object]], field_statuses: list[dict[str, object]]) -> None:
    log("Building SQLite query layer")
    connection = sqlite3.connect(path)
    try:
        connection.executescript(
            """
            PRAGMA journal_mode = WAL;
            CREATE TABLE chemicals (
                chemical_key TEXT PRIMARY KEY,
                chemical_identifier_normalized TEXT,
                chemical_identifier_type TEXT,
                chemical_identifier_status TEXT,
                chemical_names TEXT,
                source_record_count INTEGER,
                has_cbi_identity INTEGER
            );
            CREATE TABLE facilities (
                facility_id TEXT PRIMARY KEY,
                site_name TEXT,
                site_address_line1 TEXT,
                site_address_line2 TEXT,
                site_city TEXT,
                site_county_parish TEXT,
                site_state TEXT,
                site_postal_code TEXT,
                epa_facility_registry_id TEXT,
                frs_id_join_eligible INTEGER,
                latitude REAL,
                longitude REAL,
                location_status TEXT,
                source_record_count INTEGER,
                chemical_count INTEGER,
                cbi_location_record_count INTEGER,
                coordinate_variant_count INTEGER,
                has_cbi_location INTEGER
            );
            CREATE TABLE cdr_records (
                source_row_id INTEGER PRIMARY KEY,
                record_id TEXT,
                chemical_key TEXT,
                facility_id TEXT,
                chemical_identifier_normalized TEXT,
                chemical_identifier_type TEXT,
                chemical_identifier_status TEXT,
                chemical_name_normalized TEXT,
                activity_normalized TEXT,
                frs_id_normalized TEXT,
                frs_id_join_eligible INTEGER,
                latitude REAL,
                longitude REAL,
                coordinate_status TEXT,
                location_status TEXT,
                has_cbi_any INTEGER,
                has_cbi_volume INTEGER,
                has_cbi_location INTEGER,
                public_map_eligible INTEGER
            );
            CREATE TABLE volume_facts (
                source_row_id INTEGER,
                record_id TEXT,
                chemical_key TEXT,
                facility_id TEXT,
                reporting_year INTEGER,
                metric TEXT,
                value_numeric REAL,
                value_status TEXT,
                PRIMARY KEY (source_row_id, metric, reporting_year)
            );
            CREATE TABLE field_status (
                source_row_id INTEGER,
                field_name TEXT,
                status TEXT,
                PRIMARY KEY (source_row_id, field_name)
            );
            CREATE INDEX idx_cdr_records_chemical ON cdr_records (chemical_key);
            CREATE INDEX idx_cdr_records_facility ON cdr_records (facility_id);
            CREATE INDEX idx_cdr_records_map ON cdr_records (public_map_eligible);
            CREATE INDEX idx_volume_facts_metric_year ON volume_facts (metric, reporting_year);
            CREATE INDEX idx_field_status_status ON field_status (status);
            """
        )
        connection.executemany(
            "INSERT INTO chemicals VALUES (:chemical_key, :chemical_identifier_normalized, :chemical_identifier_type, :chemical_identifier_status, :chemical_names, :source_record_count, :has_cbi_identity)",
            chemicals,
        )
        connection.executemany(
            "INSERT INTO facilities VALUES (:facility_id, :site_name, :site_address_line1, :site_address_line2, :site_city, :site_county_parish, :site_state, :site_postal_code, :epa_facility_registry_id, :frs_id_join_eligible, :latitude, :longitude, :location_status, :source_record_count, :chemical_count, :cbi_location_record_count, :coordinate_variant_count, :has_cbi_location)",
            facilities,
        )
        connection.executemany(
            "INSERT INTO cdr_records VALUES (:source_row_id, :record_id, :chemical_key, :facility_id, :chemical_identifier_normalized, :chemical_identifier_type, :chemical_identifier_status, :chemical_name_normalized, :activity_normalized, :frs_id_normalized, :frs_id_join_eligible, :latitude, :longitude, :coordinate_status, :location_status, :has_cbi_any, :has_cbi_volume, :has_cbi_location, :public_map_eligible)",
            records,
        )
        volume_rows = []
        for row in volumes:
            value = None if not row["value_numeric"] else float(row["value_numeric"])
            volume_rows.append({**row, "value_numeric": value})
        connection.executemany(
            "INSERT INTO volume_facts VALUES (:source_row_id, :record_id, :chemical_key, :facility_id, :reporting_year, :metric, :value_numeric, :value_status)",
            volume_rows,
        )
        connection.executemany(
            "INSERT INTO field_status VALUES (:source_row_id, :field_name, :status)",
            field_statuses,
        )
        connection.commit()
    finally:
        connection.close()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the Phase 1 CDR mapping data layer.")
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--output-dir", type=Path, default=None)
    parser.add_argument("--encoding", default=DEFAULT_ENCODING)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    source = args.source.resolve()
    if not source.exists():
        raise FileNotFoundError(f"Source CSV not found: {source}")
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = (args.output_dir or ROOT / "outputs" / f"cdr_mapping_phase1_{timestamp}").resolve()
    output_dir.mkdir(parents=True, exist_ok=False)

    log(f"Source: {source}")
    log(f"Output: {output_dir}")
    source_hash = hashlib.sha256()
    with source.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            source_hash.update(chunk)
    log(f"Source SHA-256: {source_hash.hexdigest()}")

    records = []
    volume_facts = []
    field_statuses = []
    chemical_aggregate: dict[str, dict[str, object]] = {}
    facility_aggregate: dict[str, dict[str, object]] = {}
    status_counts: dict[str, Counter[str]] = defaultdict(Counter)
    activity_values = Counter()
    identifier_types = Counter()
    candidate_keys = Counter()
    candidate_key_volume_values: dict[str, set[str]] = defaultdict(set)
    malformed_rows = 0
    duplicate_source_row_ids = 0
    frs_id_scientific_notation_rows = 0
    source_row_ids = set()

    log("Reading and normalizing source rows")
    with source.open("r", encoding=args.encoding, errors="replace", newline="") as handle:
        reader = csv.DictReader(handle)
        source_headers = reader.fieldnames or []
        if not source_headers:
            raise ValueError("Source CSV has no header row")
        required_headers = {"CHEMICAL ID", "CHEMICAL ID TYPE", "SITE NAME", "ACTIVITY", "2023 PV"}
        missing_headers = sorted(required_headers - set(source_headers))
        if missing_headers:
            raise ValueError(f"Source CSV is missing required columns: {missing_headers}")

        clean_record_headers = ["source_row_id"] + source_headers + [field for field in DERIVED_RECORD_FIELDS if field not in source_headers and field != "source_row_id"]
        records_path = output_dir / "cdr_records.csv"
        volumes_path = output_dir / "volume_facts.csv"
        statuses_path = output_dir / "field_status.csv"
        with records_path.open("w", encoding="utf-8", newline="") as records_handle, volumes_path.open("w", encoding="utf-8", newline="") as volumes_handle, statuses_path.open("w", encoding="utf-8", newline="") as statuses_handle:
            record_writer = csv.DictWriter(records_handle, fieldnames=clean_record_headers, extrasaction="ignore")
            volume_writer = csv.DictWriter(volumes_handle, fieldnames=["source_row_id", "record_id", "chemical_key", "facility_id", "reporting_year", "metric", "value_numeric", "value_status"], extrasaction="ignore")
            status_writer = csv.DictWriter(statuses_handle, fieldnames=["source_row_id", "field_name", "status"], extrasaction="ignore")
            record_writer.writeheader()
            volume_writer.writeheader()
            status_writer.writeheader()

            for source_row_id, raw_row in enumerate(reader, start=2):
                if raw_row.get(None):
                    malformed_rows += 1
                row = {}
                statuses = {}
                for field in source_headers:
                    safe_value, status = classify_value(raw_row.get(field, ""))
                    row[field] = safe_value
                    statuses[field] = status
                    status_counts[field][status] += 1
                    if status in {CBI, NKRA, NOT_APPLICABLE}:
                        status_writer.writerow({"source_row_id": source_row_id, "field_name": field, "status": status})
                        field_statuses.append({"source_row_id": source_row_id, "field_name": field, "status": status})

                if source_row_id in source_row_ids:
                    duplicate_source_row_ids += 1
                source_row_ids.add(source_row_id)

                identifier_normalized, identifier_type, identifier_status = normalize_identifier(row, statuses)
                identifier_key = f"{identifier_type}:{identifier_normalized}" if identifier_normalized else f"REDACTED_CHEMICAL:{source_row_id}"
                chemical_name_normalized = normalize_key(row.get("CHEMICAL NAME", ""))
                frs_id_source = row.get("EPA FACILITY REGISTRY ID", "")
                frs_id = normalize_frs_id(frs_id_source) if statuses.get("EPA FACILITY REGISTRY ID") == DISCLOSED else ""
                frs_id_join_eligible = int(bool(frs_id) and "e" not in frs_id_source.lower())
                frs_id_scientific_notation_rows += int(bool(frs_id) and "e" in frs_id_source.lower())
                site_has_cbi = any(statuses.get(field) == CBI for field in LOCATION_FIELDS)
                latitude, longitude, coordinate_state = coordinate_status(row, statuses, site_has_cbi)
                facility_id = build_facility_id(row, statuses, frs_id, frs_id_source, source_row_id)
                current_location_status = location_status(row, statuses, coordinate_state, frs_id)
                activity = row.get("ACTIVITY", "")
                activity_values[activity or "MISSING"] += 1
                identifier_types[identifier_type or "MISSING"] += 1
                has_cbi_volume = any(statuses.get(field) == CBI for field, _, _ in VOLUME_FIELDS)
                has_cbi_any = any(status == CBI for status in statuses.values())
                public_map_eligible = coordinate_state == "SOURCE_COORDINATE" and current_location_status == "SOURCE_COORDINATE"
                derived = {
                    "record_id": f"cdr:{source_row_id}",
                    "chemical_key": identifier_key,
                    "facility_id": facility_id,
                    "chemical_identifier_normalized": identifier_normalized,
                    "chemical_identifier_type": identifier_type,
                    "chemical_identifier_status": identifier_status,
                    "chemical_name_normalized": chemical_name_normalized,
                    "activity_normalized": normalize_key(activity),
                    "frs_id_normalized": frs_id,
                    "frs_id_join_eligible": frs_id_join_eligible,
                    "coordinate_status": coordinate_state,
                    "location_status": current_location_status,
                    "has_cbi_any": int(has_cbi_any),
                    "has_cbi_volume": int(has_cbi_volume),
                    "has_cbi_location": int(site_has_cbi),
                    "public_map_eligible": int(public_map_eligible),
                }
                output_row = {**row, **derived, "source_row_id": source_row_id}
                record_writer.writerow(output_row)
                record_core = {
                    "source_row_id": source_row_id,
                    **derived,
                    "latitude": latitude,
                    "longitude": longitude,
                }
                records.append(record_core)

                chemical = chemical_aggregate.setdefault(
                    identifier_key,
                    {
                        "chemical_key": identifier_key,
                        "chemical_identifier_normalized": identifier_normalized,
                        "chemical_identifier_type": identifier_type,
                        "chemical_identifier_status": identifier_status,
                        "chemical_names": set(),
                        "source_record_count": 0,
                        "has_cbi_identity": 0,
                    },
                )
                if chemical_name_normalized:
                    chemical["chemical_names"].add(chemical_name_normalized)
                chemical["source_record_count"] += 1
                chemical["has_cbi_identity"] = int(chemical["has_cbi_identity"] or statuses.get("CHEMICAL NAME") == CBI or identifier_status == CBI)

                facility = facility_aggregate.setdefault(
                    facility_id,
                    {
                        "facility_id": facility_id,
                        "site_name": row.get("SITE NAME", ""),
                        "site_address_line1": row.get("SITE ADDRESS LINE1", ""),
                        "site_address_line2": row.get("SITE ADDRESS LINE2", ""),
                        "site_city": row.get("SITE CITY", ""),
                        "site_county_parish": row.get("SITE COUNTY / PARISH", ""),
                        "site_state": row.get("SITE STATE", ""),
                        "site_postal_code": row.get("SITE POSTAL CODE", ""),
                        "epa_facility_registry_id": frs_id,
                        "frs_id_join_eligible": frs_id_join_eligible,
                        "latitude": latitude,
                        "longitude": longitude,
                        "location_status": current_location_status,
                        "source_record_count": 0,
                        "chemical_keys": set(),
                        "cbi_location_record_count": 0,
                        "coordinates": set(),
                        "has_cbi_location": 0,
                    },
                )
                facility["source_record_count"] += 1
                facility["chemical_keys"].add(identifier_key)
                facility["cbi_location_record_count"] += int(site_has_cbi)
                facility["has_cbi_location"] = int(facility["has_cbi_location"] or site_has_cbi)
                if latitude and longitude:
                    facility["coordinates"].add((latitude, longitude))
                if not facility["latitude"] and latitude:
                    facility["latitude"] = latitude
                    facility["longitude"] = longitude

                for field, reporting_year, metric in VOLUME_FIELDS:
                    numeric_value, value_status = parse_number(row.get(field, ""), statuses.get(field, MISSING))
                    volume_row = {
                        "source_row_id": source_row_id,
                        "record_id": derived["record_id"],
                        "chemical_key": identifier_key,
                        "facility_id": facility_id,
                        "reporting_year": reporting_year,
                        "metric": metric,
                        "value_numeric": numeric_value,
                        "value_status": value_status,
                    }
                    volume_writer.writerow(volume_row)
                    volume_facts.append(volume_row)
                    if value_status == CBI:
                        pass
                    candidate_key = f"{identifier_key}|{facility_id}|{metric}|{reporting_year}"
                    candidate_keys[candidate_key] += 1
                    if numeric_value:
                        candidate_key_volume_values[candidate_key].add(numeric_value)

                if source_row_id % 5000 == 0:
                    log(f"Processed {source_row_id - 1:,} source rows")

    log(f"Finished normalization: {len(records):,} records")

    chemicals = []
    for chemical in chemical_aggregate.values():
        chemicals.append({**chemical, "chemical_names": " | ".join(sorted(chemical["chemical_names"]))})
    facilities = []
    for facility in facility_aggregate.values():
        facility_row = dict(facility)
        facility_row.pop("chemical_keys", None)
        facility_row.pop("coordinates", None)
        facility_row["chemical_count"] = len(facility["chemical_keys"])
        facility_row["coordinate_variant_count"] = len(facility["coordinates"])
        facilities.append(facility_row)
    for row in chemicals:
        row["has_cbi_identity"] = int(row["has_cbi_identity"])
    for row in facilities:
        row["has_cbi_location"] = int(row["has_cbi_location"])

    write_csv(output_dir / "chemicals.csv", list(chemicals[0].keys()) if chemicals else ["chemical_key"], chemicals)
    write_csv(output_dir / "facilities.csv", list(facilities[0].keys()) if facilities else ["facility_id"], facilities)

    candidate_duplicate_groups = sum(1 for count in candidate_keys.values() if count > 1)
    conflicting_duplicate_groups = sum(1 for key, values in candidate_key_volume_values.items() if candidate_keys[key] > 1 and len(values) > 1)
    cbi_field_counts = {field: counts[CBI] for field, counts in status_counts.items() if counts[CBI]}
    quality_report = {
        "dataset": "2024 CDR Consumer and Commercial Use Information",
        "grain": "one normalized row per source CSV data row; source_row_id is the source record key",
        "source": str(source),
        "source_sha256": source_hash.hexdigest(),
        "source_encoding": args.encoding,
        "source_row_count": len(records),
        "source_column_count": len(source_headers),
        "source_columns": source_headers,
        "unique_chemical_keys": len(chemicals),
        "unique_facility_keys": len(facilities),
        "public_facility_keys": sum(not row["facility_id"].startswith("REDACTED_RECORD:") for row in facilities),
        "redacted_record_facility_keys": sum(row["facility_id"].startswith("REDACTED_RECORD:") for row in facilities),
        "frs_id_join_eligible_rows": sum(row["frs_id_join_eligible"] for row in records),
        "frs_id_scientific_notation_rows": frs_id_scientific_notation_rows,
        "public_coordinate_records": sum(row["public_map_eligible"] for row in records),
        "location_status_counts": dict(Counter(row["location_status"] for row in records)),
        "coordinate_status_counts": dict(Counter(row["coordinate_status"] for row in records)),
        "cbi_rows": sum(row["has_cbi_any"] for row in records),
        "cbi_volume_rows": sum(row["has_cbi_volume"] for row in records),
        "cbi_location_rows": sum(row["has_cbi_location"] for row in records),
        "cbi_field_counts": cbi_field_counts,
        "activity_values": dict(activity_values),
        "identifier_types": dict(identifier_types),
        "malformed_rows_with_extra_columns": malformed_rows,
        "duplicate_source_row_ids": duplicate_source_row_ids,
        "candidate_duplicate_groups": candidate_duplicate_groups,
        "conflicting_candidate_duplicate_groups": conflicting_duplicate_groups,
        "volume_fact_count": len(volume_facts),
        "notes": [
            "CBI, NKRA, and not-applicable sentinel values are blanked in derived CSV and SQLite outputs; field_status.csv records their statuses.",
            "No CBI value is used as a numeric value, total, map size, or map coordinate.",
            "public_map_eligible is true only for a complete valid source coordinate with no CBI location field on the record.",
            "Facility keys prefer public site identity fields; scientific-notation FRS values are retained but not treated as exact join keys.",
            "Candidate duplicate groups require grain review before volume aggregation.",
        ],
    }
    (output_dir / "quality_report.json").write_text(json.dumps(quality_report, indent=2), encoding="utf-8")

    report_lines = [
        "CDR mapping Phase 1 quality report",
        "===================================",
        f"Source rows: {len(records):,}",
        f"Source columns: {len(source_headers):,}",
        f"Unique chemical keys: {len(chemicals):,}",
        f"Unique facility keys including opaque CBI records: {len(facilities):,}",
        f"Public facility keys: {quality_report['public_facility_keys']:,}",
        f"Opaque CBI record facility keys: {quality_report['redacted_record_facility_keys']:,}",
        f"FRS IDs eligible for exact joins: {quality_report['frs_id_join_eligible_rows']:,}",
        f"FRS IDs supplied in scientific notation and held for review: {quality_report['frs_id_scientific_notation_rows']:,}",
        f"Public source-coordinate records: {quality_report['public_coordinate_records']:,}",
        f"Rows containing one or more CBI fields: {quality_report['cbi_rows']:,}",
        f"Rows containing CBI volume fields: {quality_report['cbi_volume_rows']:,}",
        f"Rows containing CBI location fields: {quality_report['cbi_location_rows']:,}",
        f"Candidate duplicate groups requiring grain review: {candidate_duplicate_groups:,}",
        f"Candidate groups with conflicting numeric values: {conflicting_duplicate_groups:,}",
        "",
        "Location status counts:",
    ]
    report_lines.extend(f"  {key}: {value:,}" for key, value in sorted(quality_report["location_status_counts"].items()))
    report_lines.extend(["", "CBI field counts:"])
    report_lines.extend(f"  {key}: {value:,}" for key, value in sorted(cbi_field_counts.items()))
    report_lines.extend(
        [
            "",
            "Interpretation:",
            "  CBI values are withheld from derived values and retained only as field-level status flags.",
            "  Public map eligibility requires a complete source coordinate and no CBI location field.",
            "  Candidate duplicates are reported for review and are not deduplicated automatically.",
        ]
    )
    (output_dir / "quality_report.txt").write_text("\n".join(report_lines) + "\n", encoding="utf-8")

    create_sqlite(output_dir / "cdr_mapping_phase1.sqlite", records, chemicals, facilities, volume_facts, field_statuses)
    manifest = {
        "phase": 1,
        "source": str(source),
        "source_sha256": source_hash.hexdigest(),
        "output_dir": str(output_dir),
        "created_at": datetime.now().isoformat(),
        "artifacts": [
            "cdr_records.csv",
            "chemicals.csv",
            "facilities.csv",
            "volume_facts.csv",
            "field_status.csv",
            "cdr_mapping_phase1.sqlite",
            "quality_report.json",
            "quality_report.txt",
        ],
        "policy": {
            "cbi_values_are_blank_in_derived_outputs": True,
            "cbi_statuses_are_preserved": True,
            "cbi_values_used_in_numeric_aggregations": False,
            "cbi_values_used_in_map_symbology": False,
        },
    }
    (output_dir / "build_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    log("Phase 1 complete")
    log(f"Quality report: {output_dir / 'quality_report.txt'}")
    log(f"SQLite database: {output_dir / 'cdr_mapping_phase1.sqlite'}")


if __name__ == "__main__":
    main()

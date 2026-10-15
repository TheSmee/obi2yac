from __future__ import annotations

import argparse
import csv
import hashlib
import json
import logging
import sqlite3
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from .database import Database

logger = logging.getLogger(__name__)

CORE_FILES = {
    "CallLogs": ("ID", "Name", "Number", "CreateDT"),
    "Listeners": ("ID", "IP", "Description", "Type", "Active"),
    "ListenerTypes": ("ID", "Type"),
    "Substitutions": ("ID", "Name", "Number", "CreateDT"),
}
CACHE_FILE = ("ID", "Name", "Number", "CreateDT")
TABLE_ORDER = ("ListenerTypes", "Substitutions", "Listeners", "CallLogs", "SubstitutionsCache")
SCHEMA_FIELDS = {
    "CallLogs": CORE_FILES["CallLogs"],
    "Listeners": CORE_FILES["Listeners"],
    "ListenerTypes": CORE_FILES["ListenerTypes"],
    "Substitutions": CORE_FILES["Substitutions"],
    "SubstitutionsCache": CACHE_FILE,
}


class MigrationError(ValueError):
    pass


def _integer(value: str, table: str, line: int, column: str) -> int:
    try:
        return int(value)
    except ValueError as exc:
        raise MigrationError(
            f"{table}.csv row {line}: {column} must contain an integer"
        ) from exc


def _timestamp(value: str, table: str, line: int) -> str:
    candidate = value.strip()
    if not candidate:
        raise MigrationError(f"{table}.csv row {line}: CreateDT is empty")

    try:
        parsed = datetime.fromisoformat(candidate.replace("Z", "+00:00"))
    except ValueError:
        parsed = None
        for date_format in (
            "%m/%d/%Y %H:%M:%S",
            "%m/%d/%Y %I:%M:%S %p",
            "%m/%d/%Y",
            "%Y-%m-%d %H:%M:%S",
        ):
            try:
                parsed = datetime.strptime(candidate, date_format)
                break
            except ValueError:
                continue
    if parsed is None:
        raise MigrationError(
            f"{table}.csv row {line}: CreateDT must be an ISO-8601 or supported "
            "Access date/time value"
        )
    timespec = "microseconds" if parsed.microsecond else "seconds"
    return parsed.isoformat(timespec=timespec)


def _read_table(
    csv_path: Path, table: str, fields: tuple[str, ...]
) -> list[dict[str, Any]]:
    if not csv_path.is_file():
        raise MigrationError(f"Required migration file not found: {csv_path.name}")

    result: list[dict[str, Any]] = []
    with csv_path.open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        headers = {
            header.strip().casefold(): header
            for header in (reader.fieldnames or [])
            if header is not None
        }
        missing = [field for field in fields if field.casefold() not in headers]
        if missing:
            raise MigrationError(
                f"{csv_path.name} is missing required column(s): {', '.join(missing)}"
            )

        for line, row in enumerate(reader, start=2):
            values = {
                field: row.get(headers[field.casefold()]) or ""
                for field in fields
            }
            record: dict[str, Any] = {
                "ID": _integer(values["ID"], table, line, "ID")
            }
            if table == "ListenerTypes":
                record["Type"] = values["Type"] or None
            elif table == "Listeners":
                ip = values["IP"]
                if not ip.strip():
                    raise MigrationError(
                        f"{table}.csv row {line}: IP must not be empty"
                    )
                if len(ip) > 50:
                    raise MigrationError(
                        f"{table}.csv row {line}: IP exceeds the 50-character Access limit"
                    )
                description = values["Description"]
                if len(description) > 50:
                    raise MigrationError(
                        f"{table}.csv row {line}: Description exceeds 50 characters"
                    )
                listener_type = (
                    _integer(values["Type"], table, line, "Type")
                    if values["Type"]
                    else None
                )
                active = _active_value(values["Active"], table, line)
                record.update(
                    IP=ip,
                    Description=description,
                    Type=listener_type,
                    Active=active,
                )
            else:
                name = values["Name"]
                number = values["Number"]
                if len(name) > 50:
                    raise MigrationError(
                        f"{table}.csv row {line}: Name exceeds the 50-character Access limit"
                    )
                if len(number) > 15:
                    raise MigrationError(
                        f"{table}.csv row {line}: Number exceeds the 15-character Access limit"
                    )
                record.update(
                    Name=name,
                    Number=number,
                    CreateDT=_timestamp(values["CreateDT"], table, line),
                )
            result.append(record)
    return result


def _active_value(value: str, table: str, line: int) -> int | None:
    normalized = value.strip().casefold()
    if not normalized:
        return None
    if normalized in {"1", "-1", "true", "yes"}:
        return 1
    if normalized in {"0", "false", "no"}:
        return 0
    raise MigrationError(
        f"{table}.csv row {line}: Active must be true, false, 1, 0, or empty"
    )


def _check_duplicates(table: str, rows: list[dict[str, Any]], key: str) -> None:
    values: set[Any] = set()
    for line, row in enumerate(rows, start=2):
        value = row[key]
        if value in values:
            raise MigrationError(
                f"{table}.csv contains duplicate {key} values (including row {line})"
            )
        values.add(value)


def _validate(rows: dict[str, list[dict[str, Any]]]) -> None:
    for table, records in rows.items():
        _check_duplicates(table, records, "ID")
    _check_duplicates("Listeners", rows["Listeners"], "IP")
    for table in ("Substitutions", "SubstitutionsCache"):
        if table in rows:
            _check_duplicates(table, rows[table], "Number")

    known_types = {row["ID"] for row in rows["ListenerTypes"]}
    known_types.add(0)
    orphans = sum(
        row["Type"] is not None and row["Type"] not in known_types
        for row in rows["Listeners"]
    )
    if orphans:
        raise MigrationError(
            f"Listeners.csv contains {orphans} row(s) with an unknown ListenerTypes ID"
        )


def _fingerprint(csv_dir: Path, filenames: list[str]) -> str:
    digest = hashlib.sha256()
    for filename in sorted(filenames):
        digest.update(filename.encode("utf-8"))
        with (csv_dir / filename).open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
    return digest.hexdigest()


def _target_is_empty(connection: sqlite3.Connection) -> bool:
    for table in ("CallLogs", "Listeners", "Substitutions", "SubstitutionsCache"):
        if connection.execute(f"SELECT 1 FROM {table} LIMIT 1").fetchone():
            return False
    return True


def import_csv(
    database_path: str | Path,
    csv_dir: str | Path,
    *,
    include_cache: bool = False,
) -> tuple[dict[str, int], bool]:
    source_dir = Path(csv_dir)
    selected_files = [f"{table}.csv" for table in CORE_FILES]
    if include_cache:
        selected_files.append("SubstitutionsCache.csv")

    rows: dict[str, list[dict[str, Any]]] = {}
    for table, fields in CORE_FILES.items():
        rows[table] = _read_table(source_dir / f"{table}.csv", table, fields)
    if include_cache:
        rows["SubstitutionsCache"] = _read_table(
            source_dir / "SubstitutionsCache.csv", "SubstitutionsCache", CACHE_FILE
        )
    _validate(rows)

    fingerprint = _fingerprint(source_dir, selected_files)
    counts = {table: len(records) for table, records in rows.items()}
    database = Database(database_path)
    database.initialize(seed_defaults=False)

    with database.connect() as connection:
        previous = connection.execute(
            "SELECT imported_counts FROM migration_runs WHERE fingerprint = ?",
            (fingerprint,),
        ).fetchone()
        if previous is not None:
            return json.loads(previous["imported_counts"]), True
        if not _target_is_empty(connection):
            raise MigrationError(
                "The target database already contains records from another import "
                "or application run; refusing to merge and risk duplicate or overwritten data"
            )

        try:
            for table in TABLE_ORDER:
                if table not in rows:
                    continue
                fields = SCHEMA_FIELDS[table]
                placeholders = ", ".join("?" for _ in fields)
                columns = ", ".join(fields)
                sql = f"INSERT INTO {table} ({columns}) VALUES ({placeholders})"
                for row in rows[table]:
                    connection.execute(sql, tuple(row[field] for field in fields))
                if table == "ListenerTypes":
                    connection.execute(
                        "INSERT OR IGNORE INTO ListenerTypes (ID, Type) VALUES (0, ?)",
                        ("Unspecified",),
                    )
            for table, imported_rows in rows.items():
                expected_count = len(imported_rows)
                if (
                    table == "ListenerTypes"
                    and all(row["ID"] != 0 for row in imported_rows)
                ):
                    expected_count += 1
                actual_count = connection.execute(
                    f"SELECT COUNT(*) FROM {table}"
                ).fetchone()[0]
                if actual_count != expected_count:
                    raise MigrationError(
                        f"{table} row-count verification failed "
                        f"(expected {expected_count}, found {actual_count})"
                    )
            foreign_key_errors = connection.execute(
                "PRAGMA foreign_key_check"
            ).fetchall()
            if foreign_key_errors:
                raise MigrationError(
                    f"SQLite foreign-key verification found "
                    f"{len(foreign_key_errors)} violation(s)"
                )
            connection.execute(
                "INSERT INTO migration_runs (fingerprint, imported_counts) VALUES (?, ?)",
                (fingerprint, json.dumps(counts, sort_keys=True)),
            )
        except sqlite3.IntegrityError as exc:
            raise MigrationError(
                "SQLite rejected imported data because of a schema or uniqueness "
                "constraint; no rows were imported"
            ) from exc

    return counts, False


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Import Access-exported CSV files into a new Obi2Yac SQLite database"
    )
    parser.add_argument("--database", required=True, help="Destination SQLite file")
    parser.add_argument("--csv-dir", required=True, help="Directory containing exported CSV files")
    parser.add_argument(
        "--include-cache",
        action="store_true",
        help="Also import SubstitutionsCache.csv (legacy lookup records)",
    )
    args = parser.parse_args()

    try:
        counts, already_imported = import_csv(
            args.database, args.csv_dir, include_cache=args.include_cache
        )
    except (MigrationError, OSError, UnicodeError, csv.Error, sqlite3.Error) as exc:
        print(f"Migration failed: {exc}", file=sys.stderr)
        return 1

    if already_imported:
        print("This exact CSV export was already imported; no changes were made.")
    else:
        print("Import completed.")
    for table, count in sorted(counts.items()):
        print(f"{table}: {count} row(s)")
    if not args.include_cache and (Path(args.csv_dir) / "SubstitutionsCache.csv").exists():
        print(
            "SubstitutionsCache.csv was not imported; pass --include-cache to "
            "preserve its legacy lookup entries."
        )
    return 0


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    raise SystemExit(main())

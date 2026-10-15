from __future__ import annotations

import csv
import tempfile
import unittest
from pathlib import Path

from obi2yac.database import Database
from obi2yac.migrate import MigrationError, import_csv


EXPORTS = {
    "CallLogs.csv": (
        ("ID", "Name", "Number", "CreateDT"),
        (("17", " Synthetic Caller ", "02065550123", "2024-02-03 04:05:06"),),
    ),
    "Listeners.csv": (
        ("ID", "IP", "Description", "Type", "Active"),
        (("8", "127.0.0.1", "Synthetic listener", "1", "True"),),
    ),
    "ListenerTypes.csv": (
        ("ID", "Type"),
        (("1", "YAC"), ("2", "NCID")),
    ),
    "Substitutions.csv": (
        ("ID", "Name", "Number", "CreateDT"),
        (("4", "", "02065550123", "2024-02-03T04:05:06"),),
    ),
    "SubstitutionsCache.csv": (
        ("ID", "Name", "Number", "CreateDT"),
        (("2", "Legacy Synthetic Name", "2065550124", "2024-02-03T04:05:06"),),
    ),
}


def write_exports(directory: Path, *, include_cache: bool = False) -> None:
    selected = dict(EXPORTS)
    if not include_cache:
        selected.pop("SubstitutionsCache.csv")
    for filename, (headers, rows) in selected.items():
        with (directory / filename).open("w", newline="", encoding="utf-8") as stream:
            writer = csv.writer(stream)
            writer.writerow(headers)
            writer.writerows(rows)


class MigrationTests(unittest.TestCase):
    def test_import_preserves_ids_empty_strings_and_relationships(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "exports"
            source.mkdir()
            write_exports(source)
            target = root / "target.sqlite3"

            counts, repeated = import_csv(target, source)
            self.assertFalse(repeated)
            self.assertEqual(counts["CallLogs"], 1)

            database = Database(target)
            with database.connect() as connection:
                call = connection.execute("SELECT * FROM CallLogs").fetchone()
                substitution = connection.execute(
                    "SELECT * FROM Substitutions"
                ).fetchone()
                listener = connection.execute("SELECT * FROM Listeners").fetchone()
                self.assertEqual(call["ID"], 17)
                self.assertEqual(call["Name"], " Synthetic Caller ")
                self.assertEqual(call["Number"], "02065550123")
                self.assertEqual(call["CreateDT"], "2024-02-03T04:05:06")
                self.assertEqual(substitution["ID"], 4)
                self.assertEqual(substitution["Name"], "")
                self.assertEqual(listener["ID"], 8)
                self.assertEqual(listener["Active"], 1)
                self.assertEqual(
                    connection.execute("PRAGMA foreign_key_check").fetchall(), []
                )

    def test_same_export_is_idempotent_and_different_export_will_not_merge(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "exports"
            source.mkdir()
            write_exports(source)
            target = root / "target.sqlite3"

            import_csv(target, source)
            counts, repeated = import_csv(target, source)
            self.assertTrue(repeated)
            self.assertEqual(counts["CallLogs"], 1)

            with (source / "CallLogs.csv").open("a", encoding="utf-8") as stream:
                stream.write("18,Another Synthetic Caller,02065550124,2024-02-03T04:05:06\n")
            with self.assertRaisesRegex(MigrationError, "already contains records"):
                import_csv(target, source)

    def test_cache_is_only_imported_when_explicitly_requested(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "exports"
            source.mkdir()
            write_exports(source, include_cache=True)
            target = root / "target.sqlite3"

            counts, _ = import_csv(target, source)
            self.assertNotIn("SubstitutionsCache", counts)

    def test_duplicate_unique_values_are_rejected_without_import(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "exports"
            source.mkdir()
            write_exports(source)
            with (source / "Substitutions.csv").open("a", encoding="utf-8") as stream:
                stream.write("5,Second Synthetic Name,02065550123,2024-02-03T04:05:06\n")

            with self.assertRaisesRegex(MigrationError, "duplicate Number"):
                import_csv(root / "target.sqlite3", source)

    def test_orphan_listener_type_is_reported(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "exports"
            source.mkdir()
            write_exports(source)
            (source / "Listeners.csv").write_text(
                "ID,IP,Description,Type,Active\n8,127.0.0.1,Synthetic,99,True\n",
                encoding="utf-8",
            )

            with self.assertRaisesRegex(MigrationError, "unknown ListenerTypes ID"):
                import_csv(root / "target.sqlite3", source)


if __name__ == "__main__":
    unittest.main()

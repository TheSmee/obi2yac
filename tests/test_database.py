from __future__ import annotations

import sqlite3
import unittest

from obi2yac.database import Database
from obi2yac.tests.helpers import TemporaryDirectoryTestCase


class DatabaseTests(TemporaryDirectoryTestCase, unittest.TestCase):
    def setUp(self) -> None:
        super().setUp()
        self.database = Database(self.temp_path / "test.sqlite3")
        self.database.initialize()

    def test_call_log_persists_and_gets_timestamp_default(self) -> None:
        row_id = self.database.log_call("Synthetic Caller", "02065550123")
        reopened = Database(self.database.path)
        with reopened.connect() as connection:
            row = connection.execute(
                "SELECT ID, Name, Number, CreateDT FROM CallLogs WHERE ID = ?",
                (row_id,),
            ).fetchone()
        self.assertEqual(row["Name"], "Synthetic Caller")
        self.assertEqual(row["Number"], "02065550123")
        self.assertTrue(row["CreateDT"])

    def test_substitution_lookup_and_cache_fallback(self) -> None:
        with self.database.connect() as connection:
            connection.execute(
                "INSERT INTO Substitutions (Name, Number) VALUES (?, ?)",
                ("Primary Name", "0655550123"),
            )
            connection.execute(
                "INSERT INTO SubstitutionsCache (Name, Number) VALUES (?, ?)",
                ("Legacy Name", "0655550124"),
            )
        self.assertEqual(self.database.lookup_name("120655550123"), "Primary Name")
        self.assertEqual(self.database.lookup_name("120655550124"), "Legacy Name")
        self.assertIsNone(self.database.lookup_name("120655550125"))

    def test_explicit_substitution_takes_priority_over_legacy_cache(self) -> None:
        with self.database.connect() as connection:
            connection.execute(
                "INSERT INTO Substitutions (Name, Number) VALUES (?, ?)",
                ("Primary Name", "5550123"),
            )
            connection.execute(
                "INSERT INTO SubstitutionsCache (Name, Number) VALUES (?, ?)",
                ("Legacy Name", "5550123"),
            )
        self.assertEqual(self.database.lookup_name("5550123"), "Primary Name")

    def test_unique_constraints_and_listener_type_foreign_key(self) -> None:
        with self.database.connect() as connection:
            connection.execute(
                "INSERT INTO Listeners (IP, Type, Active) VALUES (?, 1, 1)",
                ("127.0.0.1",),
            )
            with self.assertRaises(sqlite3.IntegrityError):
                connection.execute(
                    "INSERT INTO Listeners (IP, Type) VALUES (?, 99)",
                    ("127.0.0.2",),
                )
            with self.assertRaises(sqlite3.IntegrityError):
                connection.execute(
                    "INSERT INTO Listeners (IP) VALUES (?)", ("127.0.0.1",)
                )
            with self.assertRaises(sqlite3.IntegrityError):
                connection.execute(
                    "INSERT INTO Substitutions (Name, Number) VALUES (?, ?)",
                    ("A", "5550123"),
                )
                connection.execute(
                    "INSERT INTO Substitutions (Name, Number) VALUES (?, ?)",
                    ("B", "5550123"),
                )

    def test_default_listener_type_is_valid_and_inactive(self) -> None:
        with self.database.connect() as connection:
            connection.execute(
                "INSERT INTO Listeners (IP) VALUES (?)", ("127.0.0.1",)
            )
            listener = connection.execute(
                "SELECT Type, Active FROM Listeners WHERE IP = ?", ("127.0.0.1",)
            ).fetchone()
        self.assertEqual(listener["Type"], 0)
        self.assertIsNone(listener["Active"])
        self.assertEqual(self.database.get_active_yac_listeners(), [])

    def test_initialization_seeds_defaults_and_is_idempotent(self) -> None:
        with self.database.connect() as connection:
            listener_types = connection.execute(
                "SELECT ID, Type FROM ListenerTypes ORDER BY ID"
            ).fetchall()
            substitutions = connection.execute(
                "SELECT ID, Name, Number, CreateDT FROM Substitutions"
            ).fetchall()
            cache = connection.execute(
                "SELECT ID, Name, Number, CreateDT FROM SubstitutionsCache ORDER BY ID"
            ).fetchall()
        expected_listener_types = [(0, "Unspecified"), (1, "YAC")]
        expected_substitutions = [
            (1, "GOOGLE INC", "6502530000", "2013-02-26T00:25:02")
        ]
        expected_cache = [
            (4, "LISTYOURSELF.NE", "9145742508", "2013-02-26T00:50:27"),
            (5, "EVEREST INST", "3039965473", "2013-03-04T14:07:03"),
        ]
        self.assertEqual([tuple(row) for row in listener_types], expected_listener_types)
        self.assertEqual([tuple(row) for row in substitutions], expected_substitutions)
        self.assertEqual([tuple(row) for row in cache], expected_cache)

        self.database.initialize()

        with self.database.connect() as connection:
            listener_types = connection.execute(
                "SELECT ID, Type FROM ListenerTypes ORDER BY ID"
            ).fetchall()
            substitutions = connection.execute(
                "SELECT ID, Name, Number, CreateDT FROM Substitutions"
            ).fetchall()
            cache = connection.execute(
                "SELECT ID, Name, Number, CreateDT FROM SubstitutionsCache ORDER BY ID"
            ).fetchall()
        self.assertEqual([tuple(row) for row in listener_types], expected_listener_types)
        self.assertEqual([tuple(row) for row in substitutions], expected_substitutions)
        self.assertEqual([tuple(row) for row in cache], expected_cache)

    def test_initialization_does_not_overwrite_existing_default_ids(self) -> None:
        with self.database.connect() as connection:
            connection.execute(
                "UPDATE Substitutions SET Name = ? WHERE ID = 1",
                ("Custom Name",),
            )
            connection.execute(
                "UPDATE SubstitutionsCache SET Name = ? WHERE ID = 4",
                ("Custom Cache Name",),
            )

        self.database.initialize()

        with self.database.connect() as connection:
            substitution = connection.execute(
                "SELECT Name FROM Substitutions WHERE ID = 1"
            ).fetchone()
            cache_entry = connection.execute(
                "SELECT Name FROM SubstitutionsCache WHERE ID = 4"
            ).fetchone()
        self.assertEqual(substitution["Name"], "Custom Name")
        self.assertEqual(cache_entry["Name"], "Custom Cache Name")

    def test_newer_schema_version_is_not_silently_overwritten(self) -> None:
        with self.database.connect() as connection:
            connection.execute("PRAGMA user_version = 2")
        with self.assertRaisesRegex(sqlite3.DatabaseError, "Unsupported SQLite schema version"):
            self.database.initialize()


if __name__ == "__main__":
    unittest.main()

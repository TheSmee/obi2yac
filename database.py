from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator


SCHEMA_VERSION = 1
DEFAULT_LISTENER_TYPES = (
    (0, "Unspecified"),
    (1, "YAC"),
)
DEFAULT_SUBSTITUTIONS = (
    (1, "GOOGLE INC", "6502530000", "2013-02-26T00:25:02"),
)
DEFAULT_SUBSTITUTIONS_CACHE = (
    (4, "LISTYOURSELF.NE", "9145742508", "2013-02-26T00:50:27"),
    (5, "EVEREST INST", "3039965473", "2013-03-04T14:07:03"),
)

SCHEMA = """
CREATE TABLE IF NOT EXISTS ListenerTypes (
    ID INTEGER PRIMARY KEY AUTOINCREMENT,
    Type TEXT CHECK (Type IS NULL OR length(Type) <= 50)
);

CREATE TABLE IF NOT EXISTS CallLogs (
    ID INTEGER PRIMARY KEY AUTOINCREMENT,
    Name TEXT NOT NULL CHECK (length(Name) <= 50),
    Number TEXT NOT NULL CHECK (length(Number) <= 15),
    CreateDT TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

CREATE TABLE IF NOT EXISTS Listeners (
    ID INTEGER PRIMARY KEY AUTOINCREMENT,
    IP TEXT NOT NULL UNIQUE CHECK (length(IP) BETWEEN 1 AND 50),
    Description TEXT NOT NULL DEFAULT '' CHECK (length(Description) <= 50),
    Type INTEGER DEFAULT 0 REFERENCES ListenerTypes(ID)
        ON UPDATE RESTRICT ON DELETE RESTRICT,
    Active INTEGER CHECK (Active IS NULL OR Active IN (0, 1))
);

CREATE TABLE IF NOT EXISTS Substitutions (
    ID INTEGER PRIMARY KEY AUTOINCREMENT,
    Name TEXT NOT NULL CHECK (length(Name) <= 50),
    Number TEXT NOT NULL UNIQUE CHECK (length(Number) <= 15),
    CreateDT TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

CREATE TABLE IF NOT EXISTS SubstitutionsCache (
    ID INTEGER PRIMARY KEY AUTOINCREMENT,
    Name TEXT NOT NULL CHECK (length(Name) <= 50),
    Number TEXT NOT NULL UNIQUE CHECK (length(Number) <= 15),
    CreateDT TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

CREATE TABLE IF NOT EXISTS migration_runs (
    fingerprint TEXT PRIMARY KEY,
    imported_counts TEXT NOT NULL,
    imported_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

"""


class Database:
    def __init__(self, path: str | Path, timeout: float = 10.0) -> None:
        self.path = Path(path)
        self.timeout = timeout

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.path, timeout=self.timeout)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute(f"PRAGMA busy_timeout = {int(self.timeout * 1000)}")
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def initialize(self, *, seed_defaults: bool = True) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as connection:
            version = connection.execute("PRAGMA user_version").fetchone()[0]
            if version not in (0, SCHEMA_VERSION):
                raise sqlite3.DatabaseError(
                    f"Unsupported SQLite schema version {version}; "
                    f"this application supports version {SCHEMA_VERSION}"
                )
            connection.execute("PRAGMA journal_mode = WAL")
            connection.executescript(SCHEMA)
            if seed_defaults:
                connection.executemany(
                    "INSERT OR IGNORE INTO ListenerTypes (ID, Type) VALUES (?, ?)",
                    DEFAULT_LISTENER_TYPES,
                )
                connection.executemany(
                    """
                    INSERT OR IGNORE INTO Substitutions
                        (ID, Name, Number, CreateDT)
                    VALUES (?, ?, ?, ?)
                    """,
                    DEFAULT_SUBSTITUTIONS,
                )
                connection.executemany(
                    """
                    INSERT OR IGNORE INTO SubstitutionsCache
                        (ID, Name, Number, CreateDT)
                    VALUES (?, ?, ?, ?)
                    """,
                    DEFAULT_SUBSTITUTIONS_CACHE,
                )
            connection.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")

    def lookup_name(self, number: str) -> str | None:
        lookup_number = number[-10:]
        with self.connect() as connection:
            for table in ("Substitutions", "SubstitutionsCache"):
                row = connection.execute(
                    f"SELECT Name FROM {table} WHERE Number = ?",
                    (lookup_number,),
                ).fetchone()
                if row is not None:
                    return row["Name"]
        return None

    def log_call(self, name: str, number: str) -> int:
        with self.connect() as connection:
            cursor = connection.execute(
                "INSERT INTO CallLogs (Name, Number) VALUES (?, ?)",
                (name, number),
            )
            return int(cursor.lastrowid)

    def get_active_yac_listeners(self) -> list[sqlite3.Row]:
        with self.connect() as connection:
            return list(
                connection.execute(
                    "SELECT ID, IP FROM Listeners WHERE Active = 1 AND Type = 1"
                )
            )

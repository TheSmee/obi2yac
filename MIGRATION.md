# Access-to-SQLite migration

The migration imports CSV files exported from the original Access database.
It does not require Microsoft Access in the Python service, and it never opens
or modifies `Obi2Yac.accdb`.

## 1. Export the source tables

Open the source database read-only. Export each table using Access's
**External Data → Text File** export. Use UTF-8/Unicode text, include column
headings, and do not change the source table. Export these four required files
into one folder:

- `CallLogs.csv`: `ID,Name,Number,CreateDT`
- `Listeners.csv`: `ID,IP,Description,Type,Active`
- `ListenerTypes.csv`: `ID,Type`
- `Substitutions.csv`: `ID,Name,Number,CreateDT`

For `CreateDT`, use ISO-8601 text such as `2026-10-13 19:57:14`. To keep the
export independent of Windows locale, run a read-only Access SELECT query in
SQL View as the export source, formatting the date explicitly. Export the
query result and discard the unsaved query when done; do not change or save
anything in the original database. For example:

```sql
SELECT ID, Name, Number,
       Format([CreateDT], "yyyy-mm-dd hh:nn:ss") AS CreateDT
FROM CallLogs;
```

Use the analogous field list for `Substitutions`. If Access cannot open the
source read-only while exporting, work from a copy and leave the original
untouched. Retain every ID and export
numbers as text. Do not sort away, filter, or omit records. An empty `Type` or
`Active` field is imported as SQL `NULL`; empty names/descriptions are retained
as empty strings. Current source data was checked for null call-log names,
numbers, and timestamps, but other Access copies may differ.

`SubstitutionsCache` is an optional fifth export:

- `SubstitutionsCache.csv`: `ID,Name,Number,CreateDT`

The AutoIt lookup actively reads this table, even though the README calls it
deprecated. Export it and pass `--include-cache` if you want to preserve its
historical lookup entries. The old external lookup writers are commented out.
The importer does not load this table unless explicitly requested.

CSV exports can contain sensitive caller names and numbers. Keep the export
directory private, do not commit it, and delete it securely when no longer
needed.

## 2. Import into a new database

Run from the parent directory containing the `obi2yac` project folder with
Python 3.10 or newer:

```text
python -m obi2yac.migrate --database obi2yac/data/obi2yac.sqlite3 --csv-dir C:\private\obi2yac-export
```

To include the legacy cache table on the initial import:

```text
python -m obi2yac.migrate --database obi2yac/data/obi2yac.sqlite3 --csv-dir C:\private\obi2yac-export --include-cache
```

The target must be a new/empty database. The tool uses a transaction and
preserves primary-key IDs. It detects repeated IDs, duplicate listener IPs,
duplicate substitution numbers, unknown listener-type IDs, missing required
columns, invalid timestamps, and SQLite constraint violations. On failure,
the transaction is rolled back. Error output reports table/row and aggregate
counts only; it does not print caller names, numbers, addresses, or row values.

Importing the exact same files again is a no-op identified by a SHA-256
fingerprint stored in the database. If the files change or the destination
already contains application data from another import, the tool refuses to
merge them. Decide whether to import `SubstitutionsCache.csv` before the first
import.

## 3. Verify

The successful migration report lists imported row counts by table. Compare
these counts with the Access table row counts noted during export. Then run
SQLite integrity and relationship checks without printing record values:

```text
python -c "import sqlite3; c=sqlite3.connect(r'obi2yac/data/obi2yac.sqlite3'); c.execute('PRAGMA foreign_keys=ON'); print('integrity:', c.execute('PRAGMA integrity_check').fetchone()[0]); print('foreign keys:', c.execute('PRAGMA foreign_key_check').fetchall()); print('counts:', {t:c.execute('SELECT COUNT(*) FROM '+t).fetchone()[0] for t in ('CallLogs','Listeners','ListenerTypes','Substitutions','SubstitutionsCache')}); c.close()"
```

The importer creates a reserved `ListenerTypes` row with ID `0` and label
`Unspecified` if Access did not supply it. It exists so the specified
`Listeners.Type` default of `0` remains valid under SQLite foreign-key
enforcement. The import report counts only exported source rows, excluding
this compatibility row and the internal `migration_runs` bookkeeping table.

Keep the Access file unchanged as a backup until counts, integrity checks, and
application behavior have been reviewed. Configure the service to use the
migrated SQLite path only after verification.

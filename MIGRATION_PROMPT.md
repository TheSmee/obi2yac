# Prompt: Rebuild the SQLite database from Access

Use this prompt when you want to migrate the original `Obi2Yac.accdb` database
into a freshly created SQLite database for this Python application:

> Migrate data from the original `Obi2Yac.accdb` Access database into this
> application's SQLite database.
>
> Read `MIGRATION.md` and inspect the SQLite schema and migration
> importer before starting. Locate the Access database and existing SQLite
> database; do not assume paths or that the existing SQLite database is
> disposable.
>
> Treat the Access database as read-only. Do not modify or overwrite it.
>
> Export the required tables as described in `MIGRATION.md`, preserving
> IDs and phone numbers as text and formatting dates consistently. Export
> `SubstitutionsCache` only if its records should be migrated, and pass
> `--include-cache` only when that CSV is present. Keep exports private. Never
> print or include real caller names, phone numbers, or other personal records
> in logs, summaries, tests, or source control.
>
> The importer requires a new or empty destination and will not merge changed
> exports into a populated database. If a SQLite database already exists,
> preserve it and import into a separate staging SQLite file under
> `data/` in the project directory. If no SQLite database exists, create one
> from scratch from the Access exports using the documented importer and
> schema. Do not replace, delete, or rename an existing database or backup
> without first asking me.
>
> Verify the import report and table counts, then run `PRAGMA integrity_check`
> and `PRAGMA foreign_key_check`. Report counts and integrity results only,
> never record values. Run migration tests if the importer or schema changes.
> Report the destination database path and any migration errors. Do not perform
> cleanup unrelated to the Access-to-SQLite data migration.

The migration mechanics and verification commands are documented in
[MIGRATION.md](MIGRATION.md).

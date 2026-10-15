# Obi2Yac 2.0

Obi2Yac is a headless Python service for receiving OBi syslog events, resolving
caller names from SQLite substitutions, notifying configured YAC clients, and
recording calls. It uses only the Python standard library and is designed to
run on Windows, macOS, or Linux. It does not require Docker or a desktop
environment.

The last AutoIt release was version 1.0.0.60. This repository contains version
2.0, its Python replacement. This project is distributed under the Apache
License 2.0:
[TheSmee/obi2yac](https://github.com/TheSmee/obi2yac).

See
[IMPLEMENTATION.md](IMPLEMENTATION.md) for its compatibility notes and known
limits.

## Requirements and setup

- Python 3.10 or newer
- Network access from the OBi device to the configured UDP listener
- Optional: network access to configured YAC listener hosts, SMTP, or Pushbullet

No third-party Python packages are required.

The commands below use `python3`. Run package commands from the directory
containing the `obi2yac/` project folder unless a section says otherwise.
Check which interpreter is selected with:

```text
python3 --version
```

### Run with an INI file

1. Copy `obi2yac/config.example.ini` to `obi2yac/config.ini`.
2. Set a database path and configure the UDP listener address/port for your
   network.
3. From the parent directory containing the project folder (`obi2yac/`), start
   the service:

   ```text
   python3 -m obi2yac
   ```

To check the available command-line options before starting:

```text
python3 -m obi2yac --help
```

The application automatically reads `obi2yac/config.ini` when present,
falling back to `config.ini` in the working directory for compatibility. The
example's relative database path is resolved from the INI file's directory,
so the SQLite file remains under `obi2yac/data/`.

### Run using environment variables only

An INI file is optional. The service also starts with built-in defaults and
environment variables:

```text
python3 -m obi2yac
```

On Windows PowerShell, set process-scoped values before starting Python:

```powershell
$env:OBI2YAC_UDP_PORT = "5514"
$env:OBI2YAC_DATABASE_PATH = "obi2yac/data/obi2yac.sqlite3"
python3 -m obi2yac
```

On macOS/Linux, use `OBI2YAC_UDP_PORT=5514 OBI2YAC_DATABASE_PATH=obi2yac/data/obi2yac.sqlite3 python3 -m obi2yac`.
Environment-variable paths are relative to the current working directory;
relative paths in an INI file are relative to that INI file.
The application does not currently include a Dockerfile or Compose stack.

To send a synthetic caller-ID event through the app to a local YAC listener,
see [YAC_TESTING.md](YAC_TESTING.md) for Windows, macOS, and Linux instructions.

The service creates the SQLite database and schema on first start. It seeds
`ListenerTypes` with `0 Unspecified`, `1 YAC`, and `2 NCID`; `Substitutions`
with `1 GOOGLE INC / 6502530000 / 2013-02-26T00:25:02`; and
`SubstitutionsCache` with `4 LISTYOURSELF.NE / 9145742508 /
2013-02-26T00:50:27` and `5 EVEREST INST / 3039965473 /
2013-03-04T14:07:03`. Call logs and listeners start empty. Initialization
does not replace existing rows. The app logs to standard output and standard
error. Press Ctrl+C or send SIGTERM for a clean shutdown.

The default UDP port remains 514 for compatibility with the AutoIt version.
Ports below 1024 usually require elevated privileges on Linux; to run as an
ordinary user, set `udp_port = 5514` (or another unprivileged port) and
configure the OBi device to send syslog there. The Python program itself does
not require root. Binding to `0.0.0.0` exposes the UDP listener on every
interface; bind to a specific trusted interface when possible. Syslog traffic
is not encrypted.

## Configuration

See [config.example.ini](config.example.ini) for a complete example with
non-secret placeholder values. The service reads `config.ini` when present, meaning `obi2yac/config.ini` when
started from the parent directory containing the project folder. It falls back
to `config.ini` in the working directory, but it can start without any INI file
using environment variables and built-in defaults.
Pass `--config /path/to/file.ini` to explicitly require a particular INI file.
`OBI2YAC_CONFIG_FILE` can select an INI path when using the default startup
mode. Environment variables override INI values. Preferred container
variables are:

| INI setting | Environment variable | Default |
|---|---|---|
| *(INI file path)* | `OBI2YAC_CONFIG_FILE` | `obi2yac/config.ini`, then working-directory `config.ini`; otherwise none |
| `[network] udp_host` | `OBI2YAC_UDP_HOST` | `0.0.0.0` |
| `[network] udp_port` | `OBI2YAC_UDP_PORT` | `514` |
| `[network] yac_port` | `OBI2YAC_YAC_PORT` | `10629` |
| `[network] yac_timeout` | `OBI2YAC_YAC_TIMEOUT` | `2` seconds |
| `[database] path` | `OBI2YAC_DATABASE_PATH` | `obi2yac/data/obi2yac.sqlite3` |
| `[logging] level` | `OBI2YAC_LOG_LEVEL` | `INFO` |
| `[pushbullet] enabled` | `OBI2YAC_PUSHBULLET_ENABLED` | `false` |
| `[pushbullet] token` | `OBI2YAC_PUSHBULLET_TOKEN` | empty |
| `[pushbullet] timeout` | `OBI2YAC_PUSHBULLET_TIMEOUT` | `5` seconds |
| `[smtp] enabled` | `OBI2YAC_SMTP_ENABLED` | `false` |
| `[smtp] host` | `OBI2YAC_SMTP_HOST` | empty |
| `[smtp] port` | `OBI2YAC_SMTP_PORT` | `25` |
| `[smtp] tls` | `OBI2YAC_SMTP_TLS` | `none` |
| `[smtp] username`, `password` | `OBI2YAC_SMTP_USERNAME`, `OBI2YAC_SMTP_PASSWORD` | empty |
| `[smtp] from_name` | `OBI2YAC_SMTP_FROM_NAME` | `Obi2Yac Alert` |
| `[smtp] from_address` | `OBI2YAC_SMTP_FROM_ADDRESS` | empty |
| `[smtp] to_address` | `OBI2YAC_SMTP_TO_ADDRESS` | empty |
| `[smtp] subject` | `OBI2YAC_SMTP_SUBJECT` | `Alarm Has Been Triggered` |
| `[dtmf] enabled` | `OBI2YAC_DTMF_ENABLED` | `false` |
| `[dtmf] trigger_1` | `OBI2YAC_DTMF_TRIGGER_1` | empty |
| `[dtmf] trigger_2` | `OBI2YAC_DTMF_TRIGGER_2` | empty |
| `[dtmf] trigger_3` | `OBI2YAC_DTMF_TRIGGER_3` | empty |
| `[dtmf] start_marker` | `OBI2YAC_DTMF_START_MARKER` | AutoIt dial-start marker |
| `[dtmf] end_marker` | `OBI2YAC_DTMF_END_MARKER` | AutoIt ringback marker |
| `[dtmf] digit_marker` | `OBI2YAC_DTMF_DIGIT_MARKER` | AutoIt DTMF marker |
| `[dtmf] on_hook_marker` | `OBI2YAC_DTMF_ON_HOOK_MARKER` | AutoIt on-hook marker |

The `[dtmf]` section also accepts the source message markers. SMTP and
Pushbullet are off unless enabled. DTMF email additionally requires
`[dtmf] enabled = true`, at least one trigger, and SMTP enabled. Enabling
Pushbullet requires a token; avoid putting a real token in a committed file
and prefer the environment variable. SMTP authentication is optional; if used,
configure both username and password. Supported TLS modes are `none`,
`starttls`, and `ssl`.

The fully qualified form `OBI2YAC_<SECTION>_<OPTION>` is also accepted (for
example, `OBI2YAC_NETWORK_UDP_PORT`). Original INI option aliases are available
for existing settings: `OBI2YAC_SYSLOG_IP`, `OBI2YAC_SYSLOG_PORT`,
`OBI2YAC_PUSHBULLETLENABLE`, `OBI2YAC_PUSHBULLETKEY`,
`OBI2YAC_ENABLEDTMFTRIGGER`, `OBI2YAC_DTMFTRIGGER1` through
`OBI2YAC_DTMFTRIGGER3`, `OBI2YAC_SMTPSERVER`, `OBI2YAC_FROMNAME`,
`OBI2YAC_FROMADDRESS`, `OBI2YAC_TOADDRESS`, `OBI2YAC_EMAILSUBJECT`,
`OBI2YAC_DTMFSTART`, `OBI2YAC_DTMFEND`, `OBI2YAC_DTMFKEY`, and
`OBI2YAC_ONHOOK`. New deployments should use the preferred names in the
table. If aliases conflict, the fully qualified form takes precedence,
followed by the preferred container name, then the legacy INI name.

Boolean settings accept `true`/`false`, `yes`/`no`, `on`/`off`, and `1`/`0`.
Invalid ports, booleans, timeouts, SMTP TLS modes, or missing required
integration settings stop startup with a configuration error.

The old `Obi2Yac.ini` options for Growl and `NoBreak` are not used. Growl has
been removed. The legacy Pushbullet option was misspelled
`PushBulletlEnable`; use `[pushbullet] enabled` in the new configuration.

## Configure listeners and substitutions

There is no built-in web administration UI. Listener addresses and caller
substitutions are edited directly in the SQLite database or imported from
Access. For example, to add a YAC client and a caller substitution:

```sql
INSERT INTO ListenerTypes (ID, Type) VALUES (1, 'YAC');
INSERT INTO Listeners (IP, Description, Type, Active)
VALUES ('192.0.2.25', 'Office YAC client', 1, 1);

INSERT INTO Substitutions (Name, Number)
VALUES ('Example Contact', '2065550123');
```

Only insert the `ListenerTypes` row if it does not already exist. The
destination IP must be reachable from the host/container and accept inbound
TCP on the configured YAC port. Keep phone numbers as text. Substitution
matching uses the final ten characters of the received number, so store the
matching ten-character value. SQLite changes are read on the next call without
restarting the service.

## Behavior

- UDP messages without `[SLIC] CID to deliver:` are ignored. The original
  `'(null)' (null)` caller-ID message is ignored as well.
- Caller-ID text is parsed using the source's apostrophe-space separator.
  Matching uses the final ten characters of the incoming number, as in the
  AutoIt query; phone numbers remain text.
- A matching `Substitutions` row overrides the name in syslog. If no row
  matches, the supplied syslog name is used, or `NAME UNAVAILABLE` if it is
  empty.
- Ten- and eleven-digit numbers are displayed in the original US format; other
  values are left as received.
- Active listeners with `Type = 1` receive the original YAC `@CALL` message.
  The service reads listener rows from SQLite for each call, so edits made by a
  local SQLite administration tool are seen on the next call.
- YAC delivery opens an outbound TCP connection to each configured listener
  using `[network] yac_port` (default `10629`). The payload is UTF-8:
  `@CALL` + caller name truncated to 25 characters + `~` + formatted number.
  The source protocol adds no newline or other terminator.
- Each recognized call event is logged once. The source has no event ID or
  deduplication rule, so retransmitted caller-ID events are not deduplicated.
- Pushbullet sends the original “New House Call” note when enabled.
- DTMF email alerts are sent only when capture starts, the captured digits
  exactly match one of the configured triggers, and the configured end marker
  arrives. An on-hook marker clears partial capture. The alert subject is
  `Obi2Yac Alert: <configured subject>`, and the message identifies the
  matched trigger.

The UDP receiver queues packets and processes them in order on a worker thread.
YAC destinations are notified concurrently, with a timeout per connection, so
a slow client does not block syslog reception or other destinations.

## SQLite database

The database contains the four core tables `CallLogs`, `Listeners`,
`ListenerTypes`, and `Substitutions`. It also contains `SubstitutionsCache` to
retain a table that active AutoIt lookup SQL still reads. The external lookup
code that once populated that cache is commented out and is not ported.

For this checkout, the repository's Access data has been imported into
`obi2yac/data/obi2yac.sqlite3`. The import contains 6,218 call logs, 2 listeners, 2
source listener types, 21 substitutions, and 2 legacy cache entries. The
SQLite database also has one reserved `ListenerTypes` ID 0 row (`Unspecified`)
for the source listener-type default. This local database is ignored by Git
and should be treated as private application data.

| Table | Columns | Notes |
|---|---|---|
| `CallLogs` | `ID`, `Name`, `Number`, `CreateDT` | One row per recognized incoming caller-ID event |
| `Listeners` | `ID`, `IP`, `Description`, `Type`, `Active` | `IP` unique; only active Type 1/YAC rows are contacted |
| `ListenerTypes` | `ID`, `Type` | ID 1 is YAC, ID 2 is NCID in the original database |
| `Substitutions` | `ID`, `Name`, `Number`, `CreateDT` | Explicit local caller-name substitutions; `Number` unique |
| `SubstitutionsCache` | `ID`, `Name`, `Number`, `CreateDT` | Legacy fallback lookup table; `Number` unique |

The schema preserves integer IDs, text phone numbers, the unique listener IP
and substitution-number constraints, and the listener-type foreign key. A
reserved `ListenerTypes` row with ID `0` is inserted as `Unspecified` when
missing. This makes the source's `Listeners.Type` default of `0` valid under
SQLite foreign-key enforcement. Type ID `1` remains YAC; ID `2` (NCID) remains
unused, as in the AutoIt program. Null listener type/active values remain
possible; only `Active = 1` and `Type = 1` are broadcast.

Access fields for call-log and substitution values are nullable in the
inspected file, although the current records contain no null values. The
requested Python schema requires their name, number, and timestamp fields;
empty text values remain allowed where specified. SQLite therefore enforces
that stricter rule for future inserts. Runtime-created timestamps use UTC ISO
8601. Imported Access timestamps are kept as ISO-8601 wall-clock values without
inventing a timezone offset.

The service opens short-lived SQLite connections, enables foreign keys, uses a
10-second busy timeout, and enables WAL mode. Keep the live database on a local
filesystem. A future administration process on the NAS can share the same
persistent volume; do not open the live file directly from Windows or macOS
over SMB. Protect the database and CSV exports because they may contain caller
information.

## Access data migration

The migration is a separate standard-library tool and does not need Microsoft
Access or ODBC at Python runtime. It imports CSV exports into a new SQLite
database; it never reads or writes the original `.accdb` file. See
[MIGRATION.md](MIGRATION.md) for export, execution, constraints, and
verification instructions. [MIGRATION_PROMPT.md](MIGRATION_PROMPT.md) provides
a reusable prompt for safely preparing a future fresh migration. Once the
Access tables are exported to the four
required CSV files, run:

```text
python3 -m obi2yac.migrate --database obi2yac/data/obi2yac.sqlite3 --csv-dir C:\private\obi2yac-export
```

Add `--include-cache` only if you also exported
`SubstitutionsCache.csv`. The importer refuses unsafe merges and verifies
counts/foreign keys; it reports counts and errors without printing record
contents.

## Tests

If your current directory is the repository/project folder itself (the path
ends in `\obi2yac`, as in the examples above), run:

```text
python3 -m unittest discover -s tests -t .. -v
```

The `-t ..` option adds the parent directory to Python's import path, allowing
the tests to import the project as the `obi2yac` package. Do not omit it when
discovering from `tests/`.

Alternatively, from the parent directory containing the `obi2yac/` project
folder, run:

```text
python3 -m unittest discover -s obi2yac/tests -v
```

Tests use synthetic records and local sockets/mocks only. They do not need an
OBi device, Access database, SMTP account, or Pushbullet token.

## Logging and privacy

Logs include timestamps, severity, and component names. Irrelevant syslog
packets are not logged at normal verbosity; malformed caller-ID packets are
reported only at debug level. Caller names and numbers, Pushbullet tokens, and
SMTP passwords are not written to operational logs. The SQLite database and
Access-export CSVs do contain sensitive call information; restrict their file
permissions and access accordingly.

## Troubleshooting

- **Address already in use / permission denied:** choose an available UDP port;
  on Linux use a port above 1023 when running without elevated privileges.
- **No caller events:** verify that the OBi sends UDP syslog to the configured
  host/port and that network firewalls allow that traffic.
- **No YAC popup:** confirm a `Listeners` row has the destination IP, `Type = 1`,
  and `Active = 1`; ensure the destination accepts TCP on the configured YAC
  port (default 10629).
- **No substitution match:** the lookup compares the final ten characters of
  the received number with `Substitutions.Number` (then the optional legacy
  cache table). Keep numbers as text.
- **Migration refused:** it may have found duplicate unique values, an orphan
  listener type, malformed input, or existing target data. Review the
  aggregate error and export/validate the CSV again; the tool does not print
  caller names or numbers.

## Future deployment

Containerization and NAS configuration are intentionally out of scope for
this initial conversion. A later Dockhand stack can map host UDP 514 to an
unprivileged container UDP port such as 5514, persist the SQLite file on a
local NAS volume, and run a separate authenticated, LAN-restricted SQLite
administration tool. Do not expose an unauthenticated database editor to the
internet.

For production use, provide the database as a persistent local container
volume, set the UDP port and database path through environment variables,
restrict UDP/TCP access with the NAS firewall, and keep SMTP/Pushbullet
credentials in the container manager's secret facility where available. The
YAC port is a destination port for outbound app connections; it is not an
inbound listener port opened by this service.

## Attributions and project history

I wrote the original AutoIt application back when OBiHai was still making
stuff and I still think their stuff was awsome even though they're now gone.
My OBi200 remains in service and I still use Obi2Yac every day, but It was
time to move from AutoIt towards a Python replacement.

Acknowledgements and historical references from the original project:

- Original project: [TheSmee/obi2yac](https://github.com/thesmee/obi2yac/)
- [YAC (Yet Another Call)](https://web.archive.org/web/20160305093837/http://www.sunflowerhead.com/software/yac/)
  is accessible through the Wayback Machine; the original source thanks
  **Jensen Harris**, whose personal site is [jensenharris.com](https://jensenharris.com).
- [Pushbullet](https://www.pushbullet.com/) is the optional push-notification
  service.
- The original, now-removed Growl for Windows integration referenced
  [Growl for Windows](https://github.com/briandunnington/growl-for-windows)
  and **Markus Mohnen**, author of the AutoIt Growl UDF.
- The original AutoIt helper acknowledgements name **Ward** for `Curl.au3`
  and `BinaryCall.au3`; `Curl.au3` credits libcurl by **Daniel Stenberg** and
  PolarSSL/mbed TLS by **ARM Limited**.
- The original `_StringStripChars.au3` helper credits **amel27** and
  **G. Sandler (MsCreatoR)**.
- `ASock.au3` references the
  [AutoIt forum ASock topic](https://www.autoitscript.com/forum/index.php?showtopic=45189&hl=Asock);
  the original source also thanks **zatorg** for the related array helper
  reference.

The AutoIt helper libraries remain in the source repository for historical
reference only; the Python application does not import or require them.

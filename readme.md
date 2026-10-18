# Obi2Yac 2.2

Obi2Yac is a headless Python service for receiving OBi syslog events, resolving
caller names from SQLite substitutions, notifying configured YAC clients, and
recording calls. It uses only the Python standard library and is designed to
run natively on Windows, macOS, or Linux, or in a Docker container. It does not
require a desktop environment.

The last AutoIt release was version 1.0.0.60. This repository contains version
2.2, its Python replacement. This project is distributed under the Apache
License 2.0:
[TheSmee/obi2yac](https://github.com/TheSmee/obi2yac).

See
[IMPLEMENTATION.md](IMPLEMENTATION.md) for its compatibility notes and known
limits.

## Requirements and setup

- Python 3.10 or newer
- Network access from the OBi device to the configured UDP listener
- Optional: network access to configured YAC listener hosts, an NCID server,
  SMTP, or Pushbullet

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

To send a synthetic caller-ID event through the app to a local YAC listener,
see [YAC_TESTING.md](YAC_TESTING.md) for Windows, macOS, and Linux instructions.
For the Docker deployment example, see
[the Dockhand/NAS deployment guide](docker/dockhand/stacks/YourNAS/obi2yac/Readme.md).

### Obi200 Syslog and health monitoring

On the Obi200, open **Device Admin** and configure Syslog to send to the
Obi2Yac host and its configured UDP port (`[network] udp_port`, default `514`).
Set the Syslog **Level** to `7` so the device sends the detailed messages this
service expects. Make sure the container/network forwards that UDP port to the
application.

Obi2Yac provides an HTTP health endpoint for Uptime Kuma and similar monitors:

```text
GET http://<obi2yac-host>:8080/health
```

Publish/allow TCP port `8080` from the monitoring host (or set `[health] host`
and `[health] port` to suit the deployment). On startup, the endpoint returns
HTTP `200` with status `starting` while waiting for the first Syslog datagram.
After a datagram arrives, it returns `200` while that datagram is within the
configured silence timeout. It returns `503` if the startup grace period
expires before the first datagram or after the timeout expires. The JSON
response reports status and seconds since the last datagram; it does not
include Syslog contents. It checks incoming Syslog activity only, not YAC,
Pushbullet, or database delivery.

The default silence timeout is 15 minutes. Configure `[health] timeout` or set
`OBI2YAC_HEALTH_TIMEOUT` to another positive number of minutes. Before the first
Syslog datagram arrives after startup, the endpoint reports `starting` with
HTTP `200` for this timeout interval; if no datagram arrives by then, it
reports unhealthy with HTTP `503`. A health check is useful only if the Obi
sends Syslog messages often enough while idle; verify the real interval and
set a suitable timeout to avoid false alarms. The call-state messages may
depend on telephone activity, so do not assume they are a continuous heartbeat
without observing them during an idle period. The service logs the current
Syslog health status at startup and then periodically using the configured
timeout interval.

The service creates the SQLite database and schema on first start. It seeds
`ListenerTypes` with `0 Unspecified` and `1 YAC`; `Substitutions`
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
| `[health] host` | `OBI2YAC_HEALTH_HOST` | `0.0.0.0` |
| `[health] port` | `OBI2YAC_HEALTH_PORT` | `8080` |
| `[health] timeout` | `OBI2YAC_HEALTH_TIMEOUT` | `15` minutes |
| `[ncid] enabled` | `NCID_ENABLED` or `OBI2YAC_NCID_ENABLED` | `false` |
| `[ncid] host` | `NCID_HOST` or `OBI2YAC_NCID_HOST` | empty |
| `[ncid] port` | `NCID_PORT` or `OBI2YAC_NCID_PORT` | `3333` |
| `[database] path` | `OBI2YAC_DATABASE_PATH` | `obi2yac/data/obi2yac.sqlite3` |
| `[logging] level` | `OBI2YAC_LOG_LEVEL` | `INFO` |
| `[logging] raw_syslog` | `OBI2YAC_LOG_RAW_SYSLOG` | `false` |
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

The HTTP health endpoint listens independently of the UDP Syslog port.
Restrict its network exposure to trusted monitoring systems.

For troubleshooting, set `[logging] raw_syslog = true` (or
`OBI2YAC_LOG_RAW_SYSLOG=true`) to log each received Syslog message at `DEBUG`
level. Set `OBI2YAC_LOG_LEVEL=DEBUG` as well to see those entries. Raw messages
can contain caller names, phone numbers, and other sensitive details; enable
this temporarily and protect the resulting logs.

The `[dtmf]` section also accepts the source message markers. SMTP and
Pushbullet are off unless enabled. DTMF notifications require
`[dtmf] enabled = true`, at least one trigger, and at least one enabled
delivery method (SMTP and/or Pushbullet). When both are enabled, a matching
trigger sends both an email and a Pushbullet note. Enabling Pushbullet requires
a token; avoid putting a real token in a committed file and prefer the
environment variable. SMTP authentication is optional; if used, configure both
username and password. Supported TLS modes are `none`, `starttls`, and `ssl`.

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
  Trailing NUL terminators are ignored. Matching uses the final ten characters
  of the incoming number, as in the AutoIt query; phone numbers remain text.
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
- When `[ncid] enabled = true`, Obi2Yac sends each call to the single configured
  NCID server over TCP (default port `3333`). Set `[ncid] host` or
  `NCID_HOST`/`OBI2YAC_NCID_HOST`; enabling NCID without a host is a startup
  configuration error. The line uses local date/time, the received number,
  and the resolved caller name in NCID `CALL:` format. Delivery runs on a
  separate worker with a two-second socket timeout, so an unavailable NCID
  server does not block YAC or the syslog event loop.
- Each recognized call event is logged once. The source has no event ID or
  deduplication rule, so retransmitted caller-ID events are not deduplicated.
- Pushbullet sends the original “New House Call” note when enabled, with the
  local time formatted as `M/D/YYYY h:mm:ss AM/PM`.
- DTMF alerts are sent only when capture starts, the captured digits exactly
  match one of the configured triggers, and the configured end marker arrives.
  A match is logged at `INFO` with the captured trigger. Successful email
  and/or Pushbullet delivery is separately logged at `INFO`; failures are
  logged as errors. An on-hook marker clears partial capture. Enabled SMTP and
  Pushbullet integrations each receive an alert titled
  `Obi2Yac Alert: <configured subject>` that identifies the matched trigger.

The UDP receiver queues packets and processes them in order on a worker thread.
YAC destinations are notified concurrently, with a timeout per connection, so
a slow client does not block syslog reception or other destinations.

## SQLite database

The database contains the four core tables `CallLogs`, `Listeners`,
`ListenerTypes`, and `Substitutions`. It also contains `SubstitutionsCache` to
retain a table that active AutoIt lookup SQL still reads. The external lookup
code that once populated that cache is commented out and is not ported.

For this checkout, the repository's Access data has been imported into
`obi2yac/data/obi2yac.sqlite3`. The import contains 6,222 call logs, 2 listeners, 1
source listener type, 21 substitutions, and 2 legacy cache entries. The
SQLite database also has one reserved `ListenerTypes` ID 0 row (`Unspecified`)
for the source listener-type default. This local database is ignored by Git
and should be treated as private application data.

| Table | Columns | Notes |
|---|---|---|
| `CallLogs` | `ID`, `Name`, `Number`, `CreateDT` | One row per recognized incoming caller-ID event |
| `Listeners` | `ID`, `IP`, `Description`, `Type`, `Active` | `IP` unique; only active Type 1/YAC rows are contacted |
| `ListenerTypes` | `ID`, `Type` | The current source database contains ID 1 (YAC) |
| `Substitutions` | `ID`, `Name`, `Number`, `CreateDT` | Explicit local caller-name substitutions; `Number` unique |
| `SubstitutionsCache` | `ID`, `Name`, `Number`, `CreateDT` | Legacy fallback lookup table; `Number` unique |

The schema preserves integer IDs, text phone numbers, the unique listener IP
and substitution-number constraints, and the listener-type foreign key. A
reserved `ListenerTypes` row with ID `0` is inserted as `Unspecified` when
missing. This makes the source's `Listeners.Type` default of `0` valid under
SQLite foreign-key enforcement. Type ID `1` remains YAC. Fresh databases do
not seed an NCID listener type; migrated databases preserve listener types
present in their Access exports. Null listener type/active values remain
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
reported only at debug level. Caller-event logs include whether a name was
supplied, whether a lookup matched, the active YAC listener count, and the
received and resolved caller names and numbers. Treat operational logs as
sensitive call information and restrict their access accordingly. Pushbullet
tokens and SMTP passwords are not written to operational logs. The SQLite
database and Access-export CSVs also contain sensitive call information.

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

## Docker deployment

An example Dockerfile, Compose stack, environment file, and deployment guide
are provided at
[docker/dockhand/stacks/YourNAS/obi2yac](docker/dockhand/stacks/YourNAS/obi2yac/Readme.md).
The example targets a Synology NAS with Dockhand, but can be adapted for other
Docker and Compose deployments.

The stack builds the image from the Git reference selected by `OBI2YAC_REF`,
publishes host UDP port `514` to container UDP port `5514` by default, and
persists the SQLite database using a host bind mount. The example's health
endpoint is not published by default; publish container TCP port `8080` only
if a monitoring host needs access. Its `.env` file passes configuration to the
container, including `OBI2YAC_LOG_RAW_SYSLOG` for optional raw Syslog logging.
Restrict network access to trusted hosts, protect credentials, and treat raw
Syslog logs as sensitive data. The YAC port is used for outbound connections;
it is not an inbound listener port opened by the service.

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

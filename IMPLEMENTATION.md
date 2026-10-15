# Python conversion report

## Source behavior mapped

| AutoIt behavior | Python implementation |
|---|---|
| UDP syslog listener; only handle `[SLIC] CID to deliver:` and filter null caller IDs | `obi2yac.service` queues datagrams in receive order; `obi2yac.events` parses the source delimiter and discards unrelated/null messages |
| Check local `Substitutions` and then `SubstitutionsCache` by the last ten number characters; retain supplied name or use `NAME UNAVAILABLE` | `Database.lookup_name` and `resolve_caller`; explicit substitutions take precedence over the legacy cache |
| Format 10/11 digit numbers and send `@CALL{name up to 25 chars}~{number}` to active Type 1 listener IPs on TCP 10629 | `format_phone_number`, `YacBroadcaster`; exact frame is UTF-8 with no newline or other terminator; destinations are connected concurrently |
| Add one `CallLogs` row per caller-ID event | `Database.log_call`; SQLite supplies a UTC ISO-8601 timestamp; no deduplication is possible in the original event format |
| Capture DTMF after dial-start, append the character after `" : "`, compare at dial-end, clear on on-hook, send email for configured sequences when `EnableDTMFTrigger` is on | `DtmfTracker` and `EmailNotifier`; DTMF and SMTP are independently configurable, and trigger sequences are configured locally rather than copied into source or tests |
| Optional Pushbullet note with name, formatted number, and time | `PushbulletNotifier`; credentials are configurable, HTTPS certificate verification remains enabled, and failures do not prevent local processing |
| Growl desktop notifications | Removed as requested |

## Database findings and decisions

The inspected Access database had five application tables. It contained 6,218
`CallLogs`, 2 `Listeners`, 2 `ListenerTypes`, 21 `Substitutions`, and 2
`SubstitutionsCache` rows. IDs are primary keys; `Listeners.IP`,
`Substitutions.Number`, and `SubstitutionsCache.Number` are unique. Listener
types in the source database are ID 1 `YAC` and ID 2 `NCID`; there are no
declared Access foreign-key relationships. The Python schema enforces the
requested Listener-to-ListenerType reference and seeds ID 0 as `Unspecified`,
ID 1 as `YAC`, and ID 2 as `NCID` so each supported listener type is available
in new databases. It also seeds the default `GOOGLE INC` substitution and the
two legacy cache entries `LISTYOURSELF.NE` and `EVEREST INST`; initialization
does not overwrite existing records.

The Access data in this checkout was imported read-only to
`obi2yac/data/obi2yac.sqlite3`, beside the Python package. All five source table row counts were preserved; the
SQLite `ListenerTypes` total is three because it includes the reserved ID 0
compatibility row. `PRAGMA integrity_check` returned `ok`, and
`PRAGMA foreign_key_check` reported zero violations.

Access reports call-log and substitution fields as nullable, but the inspected
records contained no null names, numbers, or timestamps. The new schema uses
the requested non-null constraints while preserving empty text as distinct
from absent input. `Listeners.Active` remains nullable; only value 1 is active.
The old cache table is retained because active source SQL reads it, although
the old API code that wrote it is commented out. Existing current source cache
records are not automatically migrated; opt in with `--include-cache`.

## Intentional differences and limits

- Container configuration can be supplied entirely through environment
  variables; a `config.ini` is optional unless explicitly selected. Preferred
  flat `OBI2YAC_*` names and original INI option aliases are documented in the
  README.
- The service defaults to UDP port 514, like AutoIt. Unprivileged Linux
  deployments should configure a port above 1023 (for example 5514); no root
  privilege is required by the application itself.
- AutoIt selected its first local address by default. Python defaults to
  `0.0.0.0` for network/container compatibility; this exposes the receiver on
  all interfaces unless configured otherwise.
- Access lookups used a `UNION` without ordering when both substitution tables
  contained a matching number. Python deterministically prefers the primary
  `Substitutions` table, then checks the legacy cache.
- Access `Now()` used the host's local clock. Runtime SQLite timestamps are
  UTC ISO-8601; imported historical date/time values are retained as ISO
  wall-clock timestamps because their original timezone is not recorded.
- OpenCNAM and Whitepages lookup calls and cache writes are commented out in
  the active AutoIt source and are not ported. Unknown callers use the name
  received in syslog, or `NAME UNAVAILABLE`.
- The source does not include a sample OBi packet or explicit event ID. The
  parser follows the source's marker and apostrophe-space split; deployments
  should validate it against a captured, sanitized packet from their OBi.
- The old Pushbullet helper disabled TLS certificate verification. The Python
  implementation intentionally uses the standard library's verified HTTPS
  defaults.
- The ODBiC binary is optional reconnaissance material, not used by this
  application and not a Python or future container dependency.

## Verification status

The test suite uses synthetic caller records, temporary SQLite databases,
local sockets, and mocked SMTP/HTTP. From the parent directory containing the
`obi2yac` project folder, run
`python -m unittest discover -s obi2yac/tests -v`. From the project folder
itself, run `python -m unittest discover -s tests -t .. -v`; `-t ..` is needed
so tests can import the project as the `obi2yac` package. No Access database
rows or secrets are used as fixtures.

In addition to the automated tests, a synthetic `Obi2Yac TEST` notification was
sent to a local YAC listener at `127.0.0.1:10629`; the user confirmed it was
received. This verifies live YAC listener interoperability for the configured
default port and payload format.

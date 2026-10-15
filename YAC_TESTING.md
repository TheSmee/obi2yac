# Testing YAC notifications

This guide tests the complete local path through the Python app: a synthetic
caller-ID event is sent to Obi2Yac over UDP, and Obi2Yac sends a notification
to a YAC listener over TCP. The test uses the seeded `GOOGLE INC` substitution
for `6502530000`, so the popup also verifies substitution lookup. No OBi device
is required.

## Before you start

- Start YAC and make sure its listener accepts TCP connections on port `10629`.
- Open two terminal windows.
- In both windows, start from the directory **above** the `obi2yac/` project
  folder. For example, if the repository is
  `C:\Users\you\Documents\GitHub\obi2yac`, the working directory should be
  `C:\Users\you\Documents\GitHub`.
- These steps use a separate `yac-test.sqlite3` database so the test call does
  not go into your normal database.

If YAC is running on a different computer, use that computer's LAN IP instead
of `127.0.0.1` in the listener setup below. The YAC computer must accept TCP
connections on port `10629` from the computer running Obi2Yac.

## Start Obi2Yac

In the first terminal, set a local-only UDP address, an unprivileged port, and
the dedicated test database, then start the app.

### Windows PowerShell

```powershell
$env:OBI2YAC_UDP_HOST = "127.0.0.1"
$env:OBI2YAC_UDP_PORT = "5514"
$env:OBI2YAC_YAC_PORT = "10629"
$env:OBI2YAC_DATABASE_PATH = "$PWD\obi2yac\data\yac-test.sqlite3"
python3 -m obi2yac
```

### macOS or Linux

```sh
export OBI2YAC_UDP_HOST=127.0.0.1
export OBI2YAC_UDP_PORT=5514
export OBI2YAC_YAC_PORT=10629
export OBI2YAC_DATABASE_PATH="$PWD/obi2yac/data/yac-test.sqlite3"
python3 -m obi2yac
```

Leave the app running. It creates the test database and schema on first start.

## Add the YAC destination and send a test event

In the second terminal, run the appropriate snippet. It adds the YAC listener
to the dedicated test database and sends a synthetic caller-ID event to the
app's local UDP port.

### Windows PowerShell

```powershell
@'
import socket
import sqlite3

db = r"obi2yac\data\yac-test.sqlite3"
with sqlite3.connect(db) as connection:
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute(
        "INSERT OR IGNORE INTO ListenerTypes (ID, Type) VALUES (1, 'YAC')"
    )
    connection.execute(
        """INSERT INTO Listeners (IP, Description, Type, Active)
           VALUES (?, ?, 1, 1)
           ON CONFLICT(IP) DO UPDATE SET Type = 1, Active = 1""",
        ("127.0.0.1", "Local YAC test"),
    )

with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sender:
    sender.sendto(
        b"[SLIC] CID to deliver: 'Test Caller' 6502530000",
        ("127.0.0.1", 5514),
    )

print("Synthetic caller-ID event sent to Obi2Yac.")
'@ | python3 -
```

### macOS or Linux

```sh
python3 - <<'PY'
import socket
import sqlite3

db = "obi2yac/data/yac-test.sqlite3"
with sqlite3.connect(db) as connection:
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute(
        "INSERT OR IGNORE INTO ListenerTypes (ID, Type) VALUES (1, 'YAC')"
    )
    connection.execute(
        """INSERT INTO Listeners (IP, Description, Type, Active)
           VALUES (?, ?, 1, 1)
           ON CONFLICT(IP) DO UPDATE SET Type = 1, Active = 1""",
        ("127.0.0.1", "Local YAC test"),
    )

with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sender:
    sender.sendto(
        b"[SLIC] CID to deliver: 'Test Caller' 6502530000",
        ("127.0.0.1", 5514),
    )

print("Synthetic caller-ID event sent to Obi2Yac.")
PY
```

You should see a YAC popup showing `GOOGLE INC` and `(650) 253-0000`. The
seeded substitution replaces the synthetic received name `Test Caller`. The
app logs that it processed a caller-ID event; it does not print caller details.
The test record is stored only in `yac-test.sqlite3`.

## If no popup appears

- Check the first terminal for a `YAC notification failed` error.
- Confirm YAC is running and listening on TCP port `10629`.
- If YAC is on another computer, replace the YAC host in the database setup
  snippet's values tuple (`("127.0.0.1", "Local YAC test")`) with that
  computer's IP address. Leave the UDP `sendto` address as `127.0.0.1`, and
  allow TCP port `10629` through the YAC computer's firewall.
- If you changed the YAC port, set `OBI2YAC_YAC_PORT` to that port when starting
  the app.
- Confirm the listener is active and has type `YAC` in the test database. The
  setup snippet above creates or activates this entry.

Press Ctrl+C in the first terminal to stop Obi2Yac when finished.

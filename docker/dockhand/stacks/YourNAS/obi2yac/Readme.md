# Obi2Yac on Docker with Dockhand

These files are one example of running Obi2Yac as a container on a Synology
NAS using Dockhand. Dockhand and this Compose configuration are my preferred
setup; Docker, Compose, and other container managers can be configured
differently.

## What this stack does

- Builds the image from the Obi2Yac GitHub repository and the branch, tag, or
  commit selected by `OBI2YAC_REF` in `.env`.
- Publishes the Syslog UDP port on the NAS. The default mapping forwards host
  port `514` to container port `5514`.
- Stores the SQLite database in `/volume1/docker/obi2yac/data` on the NAS,
  mapped to `/data` in the container using the bind mount configured in
  `compose.yaml`.

## Prepare storage and files

The example uses these Synology paths:

```text
/volume1/docker/obi2yac
/volume1/docker/obi2yac/data
```

Create both directories on the NAS before deploying. Your Synology volume
number or preferred directory layout may differ. If you change the data
directory, update the host path in the `volumes` section of `compose.yaml`.

If you already migrated an Access database, copy the migrated
`obi2yac.sqlite3` into the `data` directory before the first start:

```text
/volume1/docker/obi2yac/data/obi2yac.sqlite3
```

The container expects the database at `/data/obi2yac.sqlite3`. If the file is
not there, Obi2Yac creates and initializes a fresh database on startup. Do not
replace an existing database without making a backup first.

Copy these stack files to a directory on the NAS, for example:

```text
/volume1/docker/dockhand/stacks/YOUR_NAS/obi2yac
```

The directory should contain:

```text
.env
compose.yaml
Dockerfile
Readme.md
```

Edit `.env` for your environment before deployment. At minimum, confirm
`OBI2YAC_REF`, `TZ`, `SYSLOG_HOST_PORT`, `OBI2YAC_DATABASE_PATH`, and the UDP
settings. Replace placeholder SMTP or Pushbullet settings only if you use
those integrations. Keep real tokens and passwords private; do not publish
`.env` or include real credentials in screenshots or support logs.

`OBI2YAC_HEALTH_TIMEOUT` is measured in minutes. Set it to `15` for a
15-minute Syslog silence window. On startup, the health endpoint remains in
`starting` state with HTTP 200 for this interval while it waits for the first
Syslog datagram; after that, no recent Syslog activity results in HTTP 503.

The Compose file passes the NCID environment variables from `.env` into the
container. Set `OBI2YAC_NCID_ENABLED=true` and configure the NCID host and port
to enable it.

## Create and deploy the Dockhand stack

1. Open **Dockhand → Stack** and select **+ Create**.
2. Click the Compose-file folder icon.
3. Select `compose.yaml` under
   `/volume1/docker/dockhand/stacks/YOUR_NAS/obi2yac`.
4. Create/deploy the stack and wait for the image build and container startup
   to complete.

The Dockerfile clones the configured Obi2Yac Git reference during image build,
so the NAS needs network access to GitHub when building. Changing the source
reference or application version requires rebuilding and redeploying the
image.

## Configure the Obi200

On the Obi200, open **Device Admin** and configure Syslog to send to the NAS
address and the published Syslog host port. Set the Syslog **Level** to `7`.
The default Compose mapping is NAS UDP port `514` to container UDP port `5514`;
if you change `SYSLOG_HOST_PORT`, configure the Obi200 to use that host port.
Ensure the NAS firewall permits the UDP traffic from the Obi200.

## Test the deployment

1. Check Dockhand's container logs. Startup should report the Obi2Yac version,
   listening UDP address, database path, and health endpoint.
2. Send or wait for a Syslog datagram from the Obi200. The logs should report
   Syslog health as healthy when a packet has been received within the
   configured timeout.
3. Generate a test caller-ID event and verify the expected YAC, Pushbullet,
   or NCID notifications for the integrations you configured.
4. Confirm call records appear in the database. Back up the database before
   making manual changes.

## Health monitoring

Obi2Yac serves `GET /health` on container TCP port `8080`. It returns HTTP
`200` while waiting for the first Syslog datagram during the configured startup
grace period, then after receiving Syslog while packets continue to arrive
within `OBI2YAC_HEALTH_TIMEOUT`. It returns `503` if no first packet arrives
before the grace period expires or when the silence timeout expires. The
endpoint checks incoming Syslog activity, not
whether outbound YAC, Pushbullet, or NCID notifications succeed.

To reach the endpoint from Uptime Kuma or another host, publish container port
`8080` in `compose.yaml`:

```yaml
    ports:
      - "${SYSLOG_HOST_PORT}:5514/udp"
      - "8080:8080/tcp"
```

Then redeploy and configure an HTTP monitor for
`http://<nas-address>:8080/health`. Choose an unused host port if `8080` is
already occupied and map that port to container port `8080`. Restrict access
to the endpoint to trusted monitoring systems. Set `OBI2YAC_HEALTH_TIMEOUT`
in minutes and longer than the longest expected interval between Obi Syslog messages to
avoid false alarms.

## Editing the SQLite database

You can inspect and edit `obi2yac.sqlite3` with [DBeaver](https://dbeaver.io/)
or [sqlite-web](https://github.com/coleifer/sqlite-web). Stop the Obi2Yac
container before making direct database changes, and keep a backup. Do not
expose an unauthenticated database editor to the internet.

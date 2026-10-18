from __future__ import annotations

import json
import logging
import queue
import socketserver
import sqlite3
import threading
import time
from concurrent.futures import Future, ThreadPoolExecutor
from functools import partial
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from .config import AppConfig
from .database import Database
from .events import (
    CALLER_ID_MARKER,
    NAME_UNAVAILABLE,
    DtmfTracker,
    ResolvedCall,
    format_phone_number,
    parse_caller_id,
    resolve_caller,
)
from .integrations import (
    EmailNotifier,
    NcidClient,
    PushbulletNotifier,
    YacBroadcaster,
    send_with_logging,
    smtp_settings,
)

logger = logging.getLogger(__name__)


class Obi2YacService:
    def __init__(self, config: AppConfig) -> None:
        self.config = config
        self.database = Database(config.database_path)
        self.database.initialize()
        self.yac = YacBroadcaster(config.yac_port, config.yac_timeout)
        self.pushbullet = (
            PushbulletNotifier(config.pushbullet_token, config.pushbullet_timeout)
            if config.pushbullet_enabled
            else None
        )
        self.ncid = (
            NcidClient(config.ncid_host, config.ncid_port)
            if config.ncid_enabled
            else None
        )
        self.email = EmailNotifier(smtp_settings(config)) if config.smtp_enabled else None
        self.dtmf = DtmfTracker(
            config.dtmf_triggers if config.dtmf_enabled else (),
            config.dtmf_start,
            config.dtmf_end,
            config.dtmf_key,
            config.on_hook,
        )
        self._messages: queue.Queue[str | None] = queue.Queue(maxsize=1000)
        self._stopping = threading.Event()
        self._health_lock = threading.Lock()
        self._last_syslog_received: float | None = None
        self._started_at = time.monotonic()
        self._health_timeout_seconds = config.health_timeout * 60
        self._udp_thread: threading.Thread | None = None
        self._health_thread: threading.Thread | None = None
        self._health_log_thread: threading.Thread | None = None
        self._worker_thread: threading.Thread | None = None
        self._executor = ThreadPoolExecutor(max_workers=8, thread_name_prefix="yac")
        self._ncid_executor = (
            ThreadPoolExecutor(max_workers=1, thread_name_prefix="ncid")
            if config.ncid_enabled
            else None
        )

        service = self

        class QueueHandler(socketserver.BaseRequestHandler):
            def handle(self) -> None:
                data = self.request[0]
                service._record_syslog_received()
                try:
                    text = data.decode("utf-8", errors="replace")
                    if service.config.log_raw_syslog:
                        logger.debug("Received raw Syslog message: %r", text)
                    service._messages.put_nowait(text)
                except queue.Full:
                    logger.error("Syslog processing queue is full; dropping a packet")

        class SyslogServer(socketserver.UDPServer):
            allow_reuse_address = True
            max_packet_size = 65535

        try:
            self.server = SyslogServer(
                (config.udp_host, config.udp_port), QueueHandler
            )
        except OSError:
            self._executor.shutdown(wait=False, cancel_futures=True)
            if self._ncid_executor is not None:
                self._ncid_executor.shutdown(wait=False, cancel_futures=True)
            raise

        class HealthHandler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:
                if self.path != "/health":
                    self.send_error(404)
                    return
                status, result = service.health_status()
                response = json.dumps(result).encode("utf-8")
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(response)))
                self.end_headers()
                self.wfile.write(response)

            def log_message(self, _format: str, *args: object) -> None:
                return

        class HealthServer(ThreadingHTTPServer):
            allow_reuse_address = True
            daemon_threads = True

        try:
            self.health_server = HealthServer(
                (config.health_host, config.health_port), HealthHandler
            )
        except OSError:
            self.server.server_close()
            self._executor.shutdown(wait=False, cancel_futures=True)
            if self._ncid_executor is not None:
                self._ncid_executor.shutdown(wait=False, cancel_futures=True)
            raise

    @property
    def address(self) -> tuple[str, int]:
        host, port = self.server.server_address[:2]
        return str(host), int(port)

    @property
    def health_address(self) -> tuple[str, int]:
        host, port = self.health_server.server_address[:2]
        return str(host), int(port)

    def health_status(self) -> tuple[int, dict[str, float | str | None]]:
        with self._health_lock:
            last_received = self._last_syslog_received
            started_at = self._started_at
        now = time.monotonic()
        age = None if last_received is None else now - last_received
        startup_age = now - started_at
        starting = last_received is None and startup_age <= self._health_timeout_seconds
        healthy = age is not None and age <= self._health_timeout_seconds
        status = "starting" if starting else "healthy" if healthy else "unhealthy"
        return (
            503 if status == "unhealthy" else 200,
            {
                "status": status,
                "seconds_since_last_syslog": (
                    None if age is None else round(age, 1)
                ),
                "syslog_timeout_seconds": self._health_timeout_seconds,
            },
        )

    def _record_syslog_received(self) -> None:
        with self._health_lock:
            self._last_syslog_received = time.monotonic()

    def _log_health_status(self) -> None:
        _status_code, result = self.health_status()
        logger.info(
            "Syslog health status: %s "
            "(seconds_since_last_syslog=%s, timeout_minutes=%s)",
            result["status"],
            result["seconds_since_last_syslog"],
            self.config.health_timeout,
        )

    def _log_health_periodically(self) -> None:
        while not self._stopping.wait(self._health_timeout_seconds):
            self._log_health_status()

    def start(self) -> None:
        if self._udp_thread is not None:
            raise RuntimeError("Service has already been started")
        with self._health_lock:
            self._started_at = time.monotonic()
        self._worker_thread = threading.Thread(
            target=self._process_queue, name="syslog-processor", daemon=True
        )
        self._udp_thread = threading.Thread(
            target=self.server.serve_forever,
            kwargs={"poll_interval": 0.2},
            name="syslog-listener",
            daemon=True,
        )
        self._health_thread = threading.Thread(
            target=self.health_server.serve_forever,
            kwargs={"poll_interval": 0.2},
            name="health-server",
            daemon=True,
        )
        self._health_log_thread = threading.Thread(
            target=self._log_health_periodically,
            name="health-logger",
            daemon=True,
        )
        self._worker_thread.start()
        self._udp_thread.start()
        self._health_thread.start()
        self._log_health_status()
        self._health_log_thread.start()
        logger.info("Listening for OBi syslog on %s:%d", *self.address)
        logger.info("Health endpoint available on http://%s:%d/health", *self.health_address)

    def stop(self) -> None:
        if self._stopping.is_set():
            return
        self._stopping.set()
        if self._udp_thread is not None:
            self.server.shutdown()
            self._udp_thread.join()
        self.server.server_close()
        if self._health_thread is not None:
            self.health_server.shutdown()
            self._health_thread.join()
        self.health_server.server_close()
        if self._health_log_thread is not None:
            self._health_log_thread.join()
        self._messages.put(None)
        if self._worker_thread is not None:
            self._worker_thread.join()
        self._executor.shutdown(wait=True)
        if self._ncid_executor is not None:
            self._ncid_executor.shutdown(wait=True)
        logger.info("Obi2Yac service stopped")

    def serve_until(self, stop_event: threading.Event) -> None:
        self.start()
        try:
            stop_event.wait()
        finally:
            self.stop()

    def process_message(self, message: str) -> None:
        triggered_digits = self.dtmf.feed(message)
        if triggered_digits is not None:
            logger.info("DTMF trigger matched: %s", triggered_digits)
            if self.email is not None:
                future = self._executor.submit(
                    send_with_logging,
                    "SMTP",
                    self.email.send_dtmf_alert,
                    triggered_digits,
                )
                future.add_done_callback(
                    partial(
                        self._log_dtmf_notification, "Email", triggered_digits
                    )
                )
            if self.pushbullet is not None:
                future = self._executor.submit(
                    send_with_logging,
                    "Pushbullet",
                    self.pushbullet.send_dtmf_alert,
                    triggered_digits,
                    self.config.email_subject,
                )
                future.add_done_callback(
                    partial(
                        self._log_dtmf_notification,
                        "Pushbullet",
                        triggered_digits,
                    )
                )

        caller = parse_caller_id(message)
        if caller is None:
            if CALLER_ID_MARKER in message:
                logger.debug("Ignoring malformed caller-ID syslog packet")
            return

        try:
            call = resolve_caller(caller, self.database)
        except sqlite3.Error:
            logger.exception("Caller lookup failed; using the received caller name")
            call = ResolvedCall(
                name=caller.name or NAME_UNAVAILABLE,
                number=caller.number,
                display_number=format_phone_number(caller.number),
            )

        try:
            listeners = self.database.get_active_yac_listeners()
        except sqlite3.Error:
            logger.exception("Unable to load active YAC listeners")
            listeners = []

        logger.info(
            "Caller ID event processed "
            "(received_name=%r, received_number=%r, resolved_name=%r, "
            "display_number=%r, lookup_matched=%s, active_yac_listeners=%d)",
            caller.name,
            caller.number,
            call.name,
            call.display_number,
            call.lookup_matched,
            len(listeners),
        )

        for listener in listeners:
            future = self._executor.submit(self._send_yac, listener["IP"], call)
            future.add_done_callback(partial(self._log_background_failure, "YAC"))

        if self.pushbullet is not None:
            future = self._executor.submit(
                send_with_logging, "Pushbullet", self.pushbullet.send, call
            )
            future.add_done_callback(
                partial(self._log_background_failure, "Pushbullet")
            )

        if self.ncid is not None and self._ncid_executor is not None:
            future = self._ncid_executor.submit(self.ncid.send, call)
            future.add_done_callback(partial(self._log_background_failure, "NCID"))

        try:
            self.database.log_call(call.name, call.number)
        except sqlite3.Error:
            logger.exception("Unable to persist call log entry")

    def _process_queue(self) -> None:
        while True:
            message = self._messages.get()
            try:
                if message is None:
                    return
                self.process_message(message)
            except Exception:
                logger.exception("Unhandled error while processing a syslog packet")
            finally:
                self._messages.task_done()

    def _send_yac(self, host: str, call: ResolvedCall) -> None:
        try:
            self.yac.send(host, call)
        except OSError:
            logger.warning("Unable to reach YAC listener at %s", host)

    @staticmethod
    def _log_dtmf_notification(
        component: str, digits: str, future: Future[bool]
    ) -> None:
        try:
            sent = future.result()
        except Exception:
            logger.exception("%s DTMF notification failed", component)
            return
        if sent:
            logger.info("%s notification sent for DTMF trigger: %s", component, digits)

    @staticmethod
    def _log_background_failure(
        component: str, future: Future[None] | Future[bool]
    ) -> None:
        try:
            future.result()
        except Exception:
            logger.exception("%s background operation failed", component)

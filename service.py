from __future__ import annotations

import logging
import queue
import sqlite3
import socketserver
import threading
from concurrent.futures import Future, ThreadPoolExecutor
from functools import partial

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
        self._udp_thread: threading.Thread | None = None
        self._worker_thread: threading.Thread | None = None
        self._executor = ThreadPoolExecutor(max_workers=8, thread_name_prefix="yac")

        service = self

        class QueueHandler(socketserver.BaseRequestHandler):
            def handle(self) -> None:
                data = self.request[0]
                try:
                    text = data.decode("utf-8", errors="replace")
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
            raise

    @property
    def address(self) -> tuple[str, int]:
        host, port = self.server.server_address[:2]
        return str(host), int(port)

    def start(self) -> None:
        if self._udp_thread is not None:
            raise RuntimeError("Service has already been started")
        self._worker_thread = threading.Thread(
            target=self._process_queue, name="syslog-processor", daemon=True
        )
        self._udp_thread = threading.Thread(
            target=self.server.serve_forever,
            kwargs={"poll_interval": 0.2},
            name="syslog-listener",
            daemon=True,
        )
        self._worker_thread.start()
        self._udp_thread.start()
        logger.info("Listening for OBi syslog on %s:%d", *self.address)

    def stop(self) -> None:
        if self._stopping.is_set():
            return
        self._stopping.set()
        if self._udp_thread is not None:
            self.server.shutdown()
            self._udp_thread.join()
        self.server.server_close()
        self._messages.put(None)
        if self._worker_thread is not None:
            self._worker_thread.join()
        self._executor.shutdown(wait=True)
        logger.info("Obi2Yac service stopped")

    def serve_until(self, stop_event: threading.Event) -> None:
        self.start()
        try:
            stop_event.wait()
        finally:
            self.stop()

    def process_message(self, message: str) -> None:
        triggered_digits = self.dtmf.feed(message)
        if triggered_digits is not None and self.email is not None:
            future = self._executor.submit(
                send_with_logging,
                "SMTP",
                self.email.send_dtmf_alert,
                triggered_digits,
            )
            future.add_done_callback(partial(self._log_background_failure, "SMTP"))

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

        logger.info("Caller ID event processed; caller details withheld")

        try:
            listeners = self.database.get_active_yac_listeners()
        except sqlite3.Error:
            logger.exception("Unable to load active YAC listeners")
            listeners = []

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
        self.yac.send(host, call)

    @staticmethod
    def _log_background_failure(component: str, future: Future[None]) -> None:
        try:
            future.result()
        except Exception:
            logger.exception("%s background operation failed", component)

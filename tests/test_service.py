from __future__ import annotations

import http.client
import json
import socket
import sqlite3
import threading
import time
import unittest
from unittest.mock import patch

from obi2yac.database import Database
from obi2yac.service import Obi2YacService
from obi2yac.tests.helpers import TemporaryDirectoryTestCase, make_config


class ServiceTests(TemporaryDirectoryTestCase, unittest.TestCase):
    def test_health_status_is_logged_at_configured_interval(self) -> None:
        config = make_config(self.temp_path, health_timeout="0.15")
        service = Obi2YacService(config)
        try:
            with self.assertLogs("obi2yac.service", level="INFO") as captured:
                service.start()
                deadline = time.monotonic() + 2
                with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sender:
                    while time.monotonic() < deadline:
                        sender.sendto(b"<7> PRD:NOPriFbToTry", service.address)
                        health_reports = [
                            message
                            for message in captured.output
                            if "Syslog health status:" in message
                        ]
                        if len(health_reports) >= 2:
                            break
                        time.sleep(0.02)

                self.assertGreaterEqual(len(health_reports), 2)
                self.assertIn("Syslog health status: unhealthy", health_reports[0])
                self.assertIn("Syslog health status: healthy", health_reports[1])
        finally:
            service.stop()

    def test_health_endpoint_tracks_received_syslog_and_silence(self) -> None:
        config = make_config(self.temp_path, health_timeout="0.2")
        service = Obi2YacService(config)
        service.start()

        def read_health() -> tuple[int, dict[str, object]]:
            connection = http.client.HTTPConnection(*service.health_address, timeout=1)
            try:
                connection.request("GET", "/health")
                response = connection.getresponse()
                return response.status, json.loads(response.read())
            finally:
                connection.close()

        try:
            status, body = read_health()
            self.assertEqual(status, 503)
            self.assertEqual(body["status"], "unhealthy")
            self.assertIsNone(body["seconds_since_last_syslog"])

            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sender:
                sender.sendto(b"<7> PRD:NOPriFbToTry", service.address)

            deadline = time.monotonic() + 2
            while time.monotonic() < deadline:
                status, body = read_health()
                if status == 200:
                    break
                time.sleep(0.02)
            self.assertEqual(status, 200)
            self.assertEqual(body["status"], "healthy")
            self.assertIsInstance(body["seconds_since_last_syslog"], float)

            time.sleep(config.health_timeout + 0.05)
            status, body = read_health()
            self.assertEqual(status, 503)
            self.assertEqual(body["status"], "unhealthy")
        finally:
            service.stop()

    def test_enabled_ncid_dispatches_call_to_configured_server(self) -> None:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
            listener.bind(("127.0.0.1", 0))
            listener.listen(1)
            listener.settimeout(2)
            config = make_config(
                self.temp_path,
                ncid_enabled="true",
                ncid_host="127.0.0.1",
                ncid_port=listener.getsockname()[1],
            )
            service = Obi2YacService(config)
            try:
                service.process_message(
                    "[SLIC] CID to deliver: 'Synthetic Caller' 12065550123"
                )
                connection, _address = listener.accept()
                with connection:
                    payload = connection.recv(4096)
                self.assertIn(b"*NMBR*12065550123*NAME*Synthetic Caller*", payload)
                self.assertTrue(payload.startswith(b"CALL: *DATE*"))
                self.assertTrue(payload.endswith(b"\n"))
            finally:
                service.stop()

    def test_udp_event_resolves_logs_and_broadcasts_end_to_end(self) -> None:
        tcp_listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        tcp_listener.bind(("127.0.0.1", 0))
        tcp_listener.listen(1)
        tcp_listener.settimeout(3)
        yac_port = tcp_listener.getsockname()[1]
        received_payload: list[bytes] = []
        received = threading.Event()

        def receive_yac() -> None:
            try:
                client, _address = tcp_listener.accept()
                with client:
                    received_payload.append(client.recv(4096))
                received.set()
            except OSError:
                received.set()

        receiver = threading.Thread(target=receive_yac, daemon=True)
        receiver.start()
        udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        udp_socket.bind(("127.0.0.1", 0))
        udp_port = udp_socket.getsockname()[1]
        udp_socket.close()

        config = make_config(
            self.temp_path,
            network_udp_port=udp_port,
            network_yac_port=yac_port,
        )
        database = Database(config.database_path)
        database.initialize()
        with database.connect() as connection:
            connection.execute(
                "INSERT INTO Listeners (IP, Type, Active) VALUES (?, 1, 1)",
                ("127.0.0.1",),
            )
            connection.execute(
                "INSERT INTO Substitutions (Name, Number) VALUES (?, ?)",
                ("Synthetic Directory Name", "2065550123"),
            )

        service = Obi2YacService(config)
        service.start()
        try:
            sender = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sender.sendto(
                b"device [SLIC] CID to deliver: '' 12065550123\x00\x00",
                service.address,
            )
            sender.close()

            self.assertTrue(received.wait(3), "YAC notification was not received")
            self.assertEqual(
                received_payload,
                [b"@CALLSynthetic Directory Name~(206) 555-0123"],
            )

            deadline = time.monotonic() + 3
            while time.monotonic() < deadline:
                with database.connect() as connection:
                    rows = connection.execute(
                        "SELECT Name, Number FROM CallLogs"
                    ).fetchall()
                if rows:
                    break
                time.sleep(0.02)
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["Name"], "Synthetic Directory Name")
            self.assertEqual(rows[0]["Number"], "12065550123")
        finally:
            service.stop()
            tcp_listener.close()
            receiver.join(timeout=1)

    def test_irrelevant_udp_message_is_not_logged(self) -> None:
        config = make_config(self.temp_path)
        service = Obi2YacService(config)
        service.process_message("irrelevant synthetic syslog")
        with Database(config.database_path).connect() as connection:
            count = connection.execute("SELECT COUNT(*) FROM CallLogs").fetchone()[0]
        self.assertEqual(count, 0)
        service.stop()

    def test_caller_event_logs_received_and_resolved_details(self) -> None:
        config = make_config(self.temp_path)
        service = Obi2YacService(config)
        with service.database.connect() as connection:
            connection.execute(
                "INSERT INTO Substitutions (Name, Number) VALUES (?, ?)",
                ("Synthetic Directory Name", "2065550123"),
            )
        try:
            with self.assertLogs("obi2yac.service", level="INFO") as captured:
                service.process_message(
                    "[SLIC] CID to deliver: 'Synthetic Caller' 2065550123"
                )
            self.assertEqual(len(captured.output), 1)
            self.assertIn("received_name='Synthetic Caller'", captured.output[0])
            self.assertIn("received_number='2065550123'", captured.output[0])
            self.assertIn("resolved_name='Synthetic Directory Name'", captured.output[0])
            self.assertIn("display_number='(206) 555-0123'", captured.output[0])
            self.assertIn("lookup_matched=True", captured.output[0])
            self.assertIn("active_yac_listeners=0", captured.output[0])
        finally:
            service.stop()

    def test_unavailable_yac_listener_is_logged_without_traceback(self) -> None:
        config = make_config(self.temp_path)
        service = Obi2YacService(config)
        host = "192.0.2.25"
        with service.database.connect() as connection:
            connection.execute(
                "INSERT INTO Listeners (IP, Type, Active) VALUES (?, 1, 1)",
                (host,),
            )
        try:
            with patch.object(
                service.yac,
                "send",
                side_effect=TimeoutError("synthetic timeout"),
            ):
                with self.assertLogs("obi2yac.service", level="WARNING") as captured:
                    service.process_message(
                        "[SLIC] CID to deliver: 'Synthetic Caller' 2065550123"
                    )
                    service._executor.shutdown(wait=True)
            self.assertEqual(len(captured.output), 1)
            self.assertIn(f"Unable to reach YAC listener at {host}", captured.output[0])
            self.assertNotIn("Traceback", captured.output[0])
            self.assertNotIn("ERROR", captured.output[0])
            with service.database.connect() as connection:
                count = connection.execute(
                    "SELECT COUNT(*) FROM CallLogs"
                ).fetchone()[0]
            self.assertEqual(count, 1)
        finally:
            service.stop()

    def test_database_errors_are_logged_without_terminating_processing(self) -> None:
        config = make_config(self.temp_path)
        service = Obi2YacService(config)

        def failed_lookup(_number: str) -> str | None:
            raise sqlite3.OperationalError("synthetic database failure")

        service.database.lookup_name = failed_lookup
        try:
            with self.assertLogs("obi2yac.service", level="ERROR") as captured:
                service.process_message(
                    "[SLIC] CID to deliver: 'Synthetic Caller' 2065550123"
                )
            self.assertTrue(any("Caller lookup failed" in line for line in captured.output))
            with service.database.connect() as connection:
                count = connection.execute(
                    "SELECT COUNT(*) FROM CallLogs"
                ).fetchone()[0]
            self.assertEqual(count, 1)
        finally:
            service.stop()

    def test_dtmf_alert_uses_captured_sequence(self) -> None:
        config = make_config(
            self.temp_path,
            smtp_enabled="true",
            dtmf_enabled="true",
        )
        service = Obi2YacService(config)
        try:
            with patch.object(service.email, "send_dtmf_alert") as send_alert:
                service.process_message("DIAL START")
                service.process_message("tone : 6 DTMF DIGIT")
                service.process_message("tone : 9 DTMF DIGIT")
                service.process_message("tone : # DTMF DIGIT")
                service.process_message("DIAL END")
            send_alert.assert_called_once_with("69#")
        finally:
            service.stop()


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

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
                b"device [SLIC] CID to deliver: 'Received Synthetic Name' 2065550123",
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
            self.assertEqual(rows[0]["Number"], "2065550123")
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

    def test_disconnected_yac_client_does_not_prevent_call_logging(self) -> None:
        config = make_config(self.temp_path)
        service = Obi2YacService(config)
        with service.database.connect() as connection:
            connection.execute(
                "INSERT INTO Listeners (IP, Type, Active) VALUES (?, 1, 1)",
                ("127.0.0.1",),
            )
        try:
            with patch.object(
                service.yac,
                "send",
                side_effect=ConnectionRefusedError("synthetic disconnect"),
            ):
                with self.assertLogs("obi2yac.service", level="ERROR"):
                    service.process_message(
                        "[SLIC] CID to deliver: 'Synthetic Caller' 2065550123"
                    )
                    service._executor.shutdown(wait=True)
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

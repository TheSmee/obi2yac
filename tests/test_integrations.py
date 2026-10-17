from __future__ import annotations

import json
import socket
import threading
import unittest
from datetime import datetime, timedelta, timezone
from email import message_from_bytes
from unittest.mock import MagicMock, patch

from obi2yac.events import ResolvedCall
from obi2yac.integrations import (
    EmailNotifier,
    NcidClient,
    PushbulletNotifier,
    SmtpSettings,
    YacBroadcaster,
)


class IntegrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.call = ResolvedCall(
            name="Synthetic Caller With A Long Name Here",
            number="2065550123",
            display_number="(206) 555-0123",
        )

    def test_yac_wire_format_is_utf8_without_extra_terminator(self) -> None:
        payload = YacBroadcaster.payload(self.call)
        self.assertEqual(
            payload,
            b"@CALLSynthetic Caller With A L~(206) 555-0123",
        )
        self.assertFalse(payload.endswith(b"\n"))

    def test_ncid_line_format_and_tcp_delivery(self) -> None:
        timestamp = datetime(2026, 10, 17, 12, 55)
        payload = NcidClient.payload(self.call, timestamp)
        self.assertEqual(
            payload,
            b"CALL: *DATE*10172026*TIME*1255*LINE*POTS*NMBR*2065550123"
            b"*NAME*Synthetic Caller With A Long Name Here*\n",
        )

        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
            listener.bind(("127.0.0.1", 0))
            listener.listen(1)
            listener.settimeout(2)
            client = NcidClient("127.0.0.1", listener.getsockname()[1], timeout=1)
            sender = threading.Thread(target=client.send, args=(self.call,))
            sender.start()
            connection, _address = listener.accept()
            with connection:
                received = connection.recv(4096)
            sender.join(timeout=2)
        self.assertTrue(received.startswith(b"CALL: *DATE*"))
        self.assertTrue(
            received.endswith(b"*NAME*Synthetic Caller With A Long Name Here*\n")
        )

    def test_ncid_unavailable_server_logs_warning_without_traceback(self) -> None:
        with patch(
            "obi2yac.integrations.socket.create_connection",
            side_effect=TimeoutError,
        ):
            with self.assertLogs("obi2yac.integrations", level="WARNING") as captured:
                NcidClient("192.0.2.40", 3333).send(self.call)

        self.assertEqual(len(captured.output), 1)
        self.assertIn(
            "Unable to reach NCID server at 192.0.2.40:3333", captured.output[0]
        )
        self.assertNotIn("Traceback", captured.output[0])

    @patch("obi2yac.integrations.urlopen")
    def test_pushbullet_posts_note_with_basic_token_auth(self, urlopen: MagicMock) -> None:
        response = MagicMock()
        response.status = 200
        urlopen.return_value.__enter__.return_value = response
        timestamp = datetime(
            2026, 10, 15, 17, 28, 57, tzinfo=timezone(timedelta(hours=-4))
        )
        with patch("obi2yac.integrations.datetime") as datetime_mock:
            datetime_mock.now.return_value.astimezone.return_value = timestamp
            PushbulletNotifier("synthetic-token", 1).send(self.call)

        request = urlopen.call_args.args[0]
        self.assertEqual(request.get_method(), "POST")
        self.assertEqual(request.get_header("Authorization")[:6], "Basic ")
        payload = json.loads(request.data.decode("utf-8"))
        self.assertEqual(payload["title"], "New House Call")
        self.assertEqual(
            payload["body"],
            "Name: Synthetic Caller With A Long Name Here\n"
            "Number: (206) 555-0123\n"
            "Time: 10/15/2026 5:28:57 PM",
        )

    @patch("obi2yac.integrations.smtplib.SMTP")
    def test_email_alert_matches_original_subject_and_body(self, smtp_class: MagicMock) -> None:
        notifier = EmailNotifier(
            SmtpSettings(
                host="smtp.example.invalid",
                port=25,
                tls="none",
                username="",
                password="",
                from_name="Test Alert",
                from_address="sender@example.invalid",
                to_address="recipient@example.invalid",
                subject="Test Event",
            )
        )
        notifier.send_dtmf_alert("69#")

        server = smtp_class.return_value.__enter__.return_value
        raw_message = server.send_message.call_args.args[0]
        rendered = message_from_bytes(raw_message.as_bytes())
        self.assertEqual(rendered["Subject"], "Obi2Yac Alert: Test Event")
        self.assertIn("event received (69#)", rendered.get_payload())
        self.assertEqual(rendered["To"], "recipient@example.invalid")


if __name__ == "__main__":
    unittest.main()

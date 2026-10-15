from __future__ import annotations

import json
import unittest
from email import message_from_bytes
from unittest.mock import MagicMock, patch

from obi2yac.events import ResolvedCall
from obi2yac.integrations import (
    EmailNotifier,
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

    @patch("obi2yac.integrations.urlopen")
    def test_pushbullet_posts_note_with_basic_token_auth(self, urlopen: MagicMock) -> None:
        response = MagicMock()
        response.status = 200
        urlopen.return_value.__enter__.return_value = response
        PushbulletNotifier("synthetic-token", 1).send(self.call)

        request = urlopen.call_args.args[0]
        self.assertEqual(request.get_method(), "POST")
        self.assertEqual(request.get_header("Authorization")[:6], "Basic ")
        payload = json.loads(request.data.decode("utf-8"))
        self.assertEqual(payload["title"], "New House Call")
        self.assertIn("Name: Synthetic Caller With A Long Name Here", payload["body"])
        self.assertIn("Number: (206) 555-0123", payload["body"])

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

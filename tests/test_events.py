from __future__ import annotations

import unittest

from obi2yac.events import (
    DtmfTracker,
    NAME_UNAVAILABLE,
    format_phone_number,
    parse_caller_id,
    resolve_caller,
)


class FakeLookup:
    def __init__(self, results: dict[str, str]) -> None:
        self.results = results
        self.looked_up: list[str] = []

    def lookup_name(self, number: str) -> str | None:
        self.looked_up.append(number)
        return self.results.get(number[-10:])


class EventTests(unittest.TestCase):
    def test_parse_source_style_caller_id_event(self) -> None:
        parsed = parse_caller_id(
            "device [SLIC] CID to deliver: 'Synthetic Caller' 2065550123"
        )
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed.name, "Synthetic Caller")
        self.assertEqual(parsed.number, "2065550123")

    def test_ignore_unrelated_null_and_malformed_messages(self) -> None:
        self.assertIsNone(parse_caller_id("ordinary syslog"))
        self.assertIsNone(
            parse_caller_id("[SLIC] CID to deliver: '(null)' (null)")
        )
        self.assertIsNone(
            parse_caller_id("[SLIC] CID to deliver: malformed-without-delimiter")
        )

    def test_parse_empty_name_and_keep_phone_as_text(self) -> None:
        parsed = parse_caller_id("[SLIC] CID to deliver: '' 02065550123")
        self.assertEqual(parsed.name, "")
        self.assertEqual(parsed.number, "02065550123")

    def test_parse_number_quoted_after_unquoted_name(self) -> None:
        parsed = parse_caller_id("[SLIC] CID to deliver: Synthetic Caller '02065550123'")
        self.assertEqual(parsed.name, "Synthetic Caller")
        self.assertEqual(parsed.number, "02065550123")

    def test_phone_format_matches_original_length_rules(self) -> None:
        self.assertEqual(format_phone_number("2065550123"), "(206) 555-0123")
        self.assertEqual(format_phone_number("12065550123"), "(206) 555-0123")
        self.assertEqual(format_phone_number("0206555"), "0206555")
        self.assertEqual(format_phone_number("206-555-0123"), "206-555-0123")

    def test_substitution_overrides_received_name_using_last_ten_characters(self) -> None:
        lookup = FakeLookup({"0655501234": "Synthetic Directory Name"})
        result = resolve_caller(
            parse_caller_id("[SLIC] CID to deliver: 'Received Name' 120655501234"),
            lookup,
        )
        self.assertEqual(result.name, "Synthetic Directory Name")
        self.assertEqual(result.number, "120655501234")
        self.assertEqual(lookup.looked_up, ["120655501234"])

    def test_unknown_number_uses_received_name_then_unavailable_marker(self) -> None:
        lookup = FakeLookup({})
        received = resolve_caller(
            parse_caller_id("[SLIC] CID to deliver: 'Received Name' 2065550123"),
            lookup,
        )
        unknown = resolve_caller(
            parse_caller_id("[SLIC] CID to deliver: '' 2065550124"), lookup
        )
        self.assertEqual(received.name, "Received Name")
        self.assertEqual(unknown.name, NAME_UNAVAILABLE)

    def test_dtmf_trigger_requires_start_digits_and_end(self) -> None:
        tracker = DtmfTracker(
            ("69#",), "DIAL START", "DIAL END", "DTMF DIGIT", "ON HOOK"
        )
        self.assertIsNone(tracker.feed("DIAL START"))
        self.assertIsNone(tracker.feed("tone : 6 DTMF DIGIT"))
        self.assertIsNone(tracker.feed("tone : 9 DTMF DIGIT"))
        self.assertEqual(tracker.feed("tone : # DTMF DIGIT"), None)
        self.assertEqual(tracker.feed("DIAL END"), "69#")
        self.assertIsNone(tracker.feed("DIAL END"))

    def test_on_hook_clears_partial_dtmf_sequence(self) -> None:
        tracker = DtmfTracker(
            ("69#",), "DIAL START", "DIAL END", "DTMF DIGIT", "ON HOOK"
        )
        tracker.feed("DIAL START")
        tracker.feed("tone : 6 DTMF DIGIT")
        tracker.feed("ON HOOK")
        tracker.feed("DIAL END")
        self.assertIsNone(tracker.feed("DIAL END"))


if __name__ == "__main__":
    unittest.main()

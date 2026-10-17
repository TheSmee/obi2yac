from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


CALLER_ID_MARKER = "[SLIC] CID to deliver:"
NULL_CALL_MARKER = "'(null)' (null)"
NAME_UNAVAILABLE = "NAME UNAVAILABLE"


@dataclass(frozen=True)
class CallerId:
    name: str
    number: str


@dataclass(frozen=True)
class ResolvedCall:
    name: str
    number: str
    display_number: str


class NameLookup(Protocol):
    def lookup_name(self, number: str) -> str | None: ...


def parse_caller_id(message: str) -> CallerId | None:
    marker_at = message.find(CALLER_ID_MARKER)
    if marker_at < 0 or NULL_CALL_MARKER in message:
        return None

    payload = message[marker_at + len(CALLER_ID_MARKER) :].strip()
    payload = payload.rstrip("\x00").rstrip()
    separator_at = payload.find("' ")
    if separator_at >= 0:
        name = payload[:separator_at].strip().strip("'")
        number = payload[separator_at + 2 :].strip().strip("'")
    else:
        quoted_parts = [
            part.strip() for part in payload.split("'") if part.strip()
        ]
        if len(quoted_parts) < 2:
            return None
        name, number = quoted_parts[:2]
    return CallerId(name=name, number=number)


def format_phone_number(number: str) -> str:
    if len(number) == 11 and number.isdigit():
        return f"({number[1:4]}) {number[4:7]}-{number[7:]}"
    if len(number) == 10 and number.isdigit():
        return f"({number[:3]}) {number[3:6]}-{number[6:]}"
    return number


def resolve_caller(caller: CallerId, database: NameLookup) -> ResolvedCall:
    name = caller.name
    resolved_name = database.lookup_name(caller.number)
    if resolved_name is not None:
        name = resolved_name
    elif not name:
        name = NAME_UNAVAILABLE
    return ResolvedCall(
        name=name,
        number=caller.number,
        display_number=format_phone_number(caller.number),
    )


class DtmfTracker:
    def __init__(
        self,
        triggers: tuple[str, ...],
        start_marker: str,
        end_marker: str,
        digit_marker: str,
        on_hook_marker: str,
    ) -> None:
        self.triggers = frozenset(triggers)
        self.start_marker = start_marker
        self.end_marker = end_marker
        self.digit_marker = digit_marker
        self.on_hook_marker = on_hook_marker
        self._capturing = False
        self._digits = ""

    def feed(self, message: str) -> str | None:
        if self.start_marker and self.start_marker in message:
            self._capturing = True

        if self._capturing and self.digit_marker and self.digit_marker in message:
            separator_at = message.find(" : ")
            digit_at = separator_at + 3
            if separator_at >= 0 and digit_at < len(message):
                self._digits += message[digit_at]

        matched = None
        if self.end_marker and self.end_marker in message:
            if self._digits in self.triggers:
                matched = self._digits
            self._reset()

        if self.on_hook_marker and self.on_hook_marker in message:
            self._reset()
        return matched

    def _reset(self) -> None:
        self._capturing = False
        self._digits = ""

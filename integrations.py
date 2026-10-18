from __future__ import annotations

import base64
import http.client
import json
import logging
import smtplib
import socket
import ssl
from dataclasses import dataclass
from datetime import datetime
from email.message import EmailMessage
from typing import Callable
from urllib.error import URLError
from urllib.request import Request, urlopen

from .config import AppConfig
from .events import ResolvedCall

logger = logging.getLogger(__name__)


class YacBroadcaster:
    def __init__(self, port: int, timeout: float) -> None:
        self.port = port
        self.timeout = timeout

    @staticmethod
    def payload(call: ResolvedCall) -> bytes:
        return f"@CALL{call.name[:25]}~{call.display_number}".encode("utf-8")

    def send(self, host: str, call: ResolvedCall) -> None:
        with socket.create_connection((host, self.port), timeout=self.timeout) as client:
            client.sendall(self.payload(call))


class NcidClient:
    def __init__(self, host: str, port: int = 3333, timeout: float = 2.0) -> None:
        self.host = host
        self.port = port
        self.timeout = timeout

    @staticmethod
    def payload(call: ResolvedCall, now: datetime | None = None) -> bytes:
        timestamp = datetime.now() if now is None else now
        number = call.number.replace("*", " ").replace("\r", " ").replace("\n", " ")
        name = call.name.replace("*", " ").replace("\r", " ").replace("\n", " ")
        line = (
            f"CALL: *DATE*{timestamp:%m%d%Y}*TIME*{timestamp:%H%M}"
            f"*LINE*POTS*NMBR*{number}*NAME*{name}*\n"
        )
        return line.encode("utf-8")

    def send(self, call: ResolvedCall) -> None:
        try:
            with socket.create_connection(
                (self.host, self.port), timeout=self.timeout
            ) as client:
                client.sendall(self.payload(call))
        except OSError:
            logger.warning(
                "Unable to reach NCID server at %s:%d", self.host, self.port
            )


class PushbulletNotifier:
    endpoint = "https://api.pushbullet.com/v2/pushes"

    def __init__(self, token: str, timeout: float) -> None:
        self.token = token
        self.timeout = timeout

    def send(self, call: ResolvedCall) -> None:
        now = datetime.now().astimezone()
        hour = now.hour % 12 or 12
        meridiem = "AM" if now.hour < 12 else "PM"
        timestamp = (
            f"{now.month}/{now.day}/{now.year} "
            f"{hour}:{now.minute:02}:{now.second:02} {meridiem}"
        )
        body = {
            "type": "note",
            "title": "New House Call",
            "body": (
                f"Name: {call.name}\n"
                f"Number: {call.display_number}\n"
                f"Time: {timestamp}"
            ),
        }
        self._send_note(body["title"], body["body"])

    def send_dtmf_alert(self, digits: str, subject: str) -> None:
        self._send_note(
            f"Obi2Yac Alert: {subject}",
            f"DTMF trigger received: {digits}\nEvent type: {subject}",
        )

    def _send_note(self, title: str, body: str) -> None:
        credentials = base64.b64encode(f"{self.token}:".encode("utf-8")).decode("ascii")
        request = Request(
            self.endpoint,
            data=json.dumps({"type": "note", "title": title, "body": body}).encode(
                "utf-8"
            ),
            headers={
                "Authorization": f"Basic {credentials}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        with urlopen(request, timeout=self.timeout) as response:
            if not 200 <= response.status < 300:
                raise URLError(f"Pushbullet returned HTTP {response.status}")


@dataclass(frozen=True)
class SmtpSettings:
    host: str
    port: int
    tls: str
    username: str
    password: str
    from_name: str
    from_address: str
    to_address: str
    subject: str
    timeout: float = 10.0


class EmailNotifier:
    def __init__(self, settings: SmtpSettings) -> None:
        self.settings = settings

    def send_dtmf_alert(self, digits: str) -> None:
        message = EmailMessage()
        message["From"] = f"{self.settings.from_name} <{self.settings.from_address}>"
        message["To"] = self.settings.to_address
        message["Subject"] = f"Obi2Yac Alert: {self.settings.subject}"
        message.set_content(
            "Greetings,\n\n"
            f" Obi2Yac event received ({digits}).  Event type is: "
            f"{self.settings.subject}\n\n"
            "--\n"
            "Obi2Yac"
        )

        if self.settings.tls == "ssl":
            with smtplib.SMTP_SSL(
                self.settings.host,
                self.settings.port,
                timeout=self.settings.timeout,
                context=ssl.create_default_context(),
            ) as server:
                self._send(server, message)
            return

        with smtplib.SMTP(
            self.settings.host, self.settings.port, timeout=self.settings.timeout
        ) as server:
            if self.settings.tls == "starttls":
                server.starttls(context=ssl.create_default_context())
            self._send(server, message)

    def _send(self, server: smtplib.SMTP, message: EmailMessage) -> None:
        if self.settings.username:
            server.login(self.settings.username, self.settings.password)
        server.send_message(message)


def smtp_settings(config: AppConfig) -> SmtpSettings:
    return SmtpSettings(
        host=config.smtp_host,
        port=config.smtp_port,
        tls=config.smtp_tls,
        username=config.smtp_username,
        password=config.smtp_password,
        from_name=config.smtp_from_name,
        from_address=config.smtp_from_address,
        to_address=config.smtp_to_address,
        subject=config.email_subject,
    )


def send_with_logging(
    component: str, operation: Callable[..., None], *args: object
) -> None:
    try:
        operation(*args)
    except (
        OSError,
        URLError,
        http.client.HTTPException,
        smtplib.SMTPException,
        TimeoutError,
    ):
        logger.error(
            "%s notification failed (%s)", component, type(exc).__name__
        )

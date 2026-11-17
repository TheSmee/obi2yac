
#!/usr/bin/env python3
"""
LG webOS TV toast notification test.

Dependencies:
    python3 -m pip install websocket-client

Pairing:
    Run the original pywebostv-based script once to create lg_tv_key.json.
    This standalone script reuses that pairing key.

No pywebostv dependency is required.
"""

import copy
import json
import ssl
import uuid
from datetime import datetime
from pathlib import Path

import websocket


# ---------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------

TV_IP = "172.16.0.212"
TV_PORT = 3001
KEY_FILE = Path("lg_tv_key.json")
TIMEOUT = 10


# ---------------------------------------------------------------------
# LG webOS registration manifest
#
# Preserved from the working pywebostv 0.8.9 registration payload.
# Keep the signature and app identity unchanged.
# ---------------------------------------------------------------------

REGISTRATION_PAYLOAD = {
    "forcePairing": False,
    "manifest": {
        "appVersion": "1.1",
        "manifestVersion": 1,
        "permissions": [
            "WRITE_NOTIFICATION_TOAST",
        ],
    },
    "pairingType": "PROMPT",
}

# ---------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------

def toast_lines(*lines, pad=50):
    """Join lines with spaces to encourage toast text wrapping."""
    return (" " * pad).join(lines)


def receive_json(ws):
    """Receive and decode one JSON WebSocket message."""
    raw = ws.recv()

    if not raw:
        raise RuntimeError("The TV closed the WebSocket connection.")

    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            f"Received a non-JSON response from the TV: {raw!r}"
        ) from exc


# ---------------------------------------------------------------------
# Registration and toast
# ---------------------------------------------------------------------

def send_toast(message):
    if not KEY_FILE.is_file():
        raise FileNotFoundError(
            f"Pairing file not found: {KEY_FILE}\n"
            "Run the original pairing script first."
        )

    store = json.loads(KEY_FILE.read_text(encoding="utf-8"))
    client_key = store.get("client_key")

    if not client_key:
        raise ValueError(
            f"No client_key found in {KEY_FILE}."
        )

    payload = copy.deepcopy(REGISTRATION_PAYLOAD)
    payload["client-key"] = client_key

    url = f"wss://{TV_IP}:{TV_PORT}/"
    print(f"Connecting to {url}...")

    # Local-LAN test configuration:
    # suppress_origin=True matches pywebostv's handshake behavior.
    # CERT_NONE accepts the TV's certificate without verifying its identity.
    ws = websocket.create_connection(
        url,
        timeout=TIMEOUT,
        suppress_origin=True,
        sslopt={"cert_reqs": ssl.CERT_NONE},
    )

    try:
        # Register the already-paired client.
        register_id = str(uuid.uuid4())

        ws.send(json.dumps({
            "type": "register",
            "id": register_id,
            "payload": payload,
        }))

        print("Registering with the TV...")

        while True:
            response = receive_json(ws)

            if response.get("id") != register_id:
                continue

            response_type = response.get("type")
            response_payload = response.get("payload") or {}

            if response_type == "registered":
                print("Registration successful.")
                break

            if response_type == "error":
                raise RuntimeError(
                    f"TV registration error: {response}"
                )

            if response_payload.get("pairingType") == "PROMPT":
                print("Pairing prompt received; check the TV.")

        # Send the toast notification.
        request_id = str(uuid.uuid4())

        ws.send(json.dumps({
            "type": "request",
            "id": request_id,
            "uri": "ssap://system.notifications/createToast",
            "payload": {
                "message": message,
            },
        }))

        print("Waiting for toast response...")

        while True:
            response = receive_json(ws)

            if response.get("id") != request_id:
                continue

            if response.get("type") == "error":
                raise RuntimeError(
                    f"TV toast error: {response}"
                )

            print("Toast response:", response)
            return response

    finally:
        ws.close()


# ---------------------------------------------------------------------
# Example test
# ---------------------------------------------------------------------

if __name__ == "__main__":
    current_time = datetime.now().strftime("%I:%M %p")

    message = toast_lines(
        f"The Phone is ringing... {current_time}",
        "Name: Yac Test Call",
        "Number: (425) 555-1212",
    )

    print(f"Sending toast to {TV_IP}...")

    try:
        send_toast(message)
        print("Done.")
    except Exception as exc:
        print(f"ERROR: {exc}")
        raise

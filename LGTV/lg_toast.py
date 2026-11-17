import json
from datetime import datetime
from pathlib import Path
from pywebostv.connection import WebOSClient
from pywebostv.controls import SystemControl

TV_IP = "172.16.0.212"
KEY_FILE = Path("lg_tv_key.json")

def toast_lines(*lines, pad=50):
    """Join lines with enough spaces to force wrapping."""
    return (" " * pad).join(lines)

# Load existing key if we have one
store = {}
if KEY_FILE.exists():
    store = json.loads(KEY_FILE.read_text())

print(f"Connecting to {TV_IP}...")
client = WebOSClient(TV_IP, secure=True)
client.connect()

print("Registering...")
for status in client.register(store):
    if status == WebOSClient.PROMPTED:
        print("→ Accept the connection prompt on the TV")
    elif status == WebOSClient.REGISTERED:
        print("→ Paired")
        # Save the key for next time
        KEY_FILE.write_text(json.dumps(store))

print("Sending toast...")
system = SystemControl(client)
current_time = datetime.now().strftime("%I:%M %p")
system.notify(toast_lines(
    f"The Phone is ringing... {current_time}",
    "Name: Yac Test Call",
    "Number: (425) 555-1212"
))

print("Done")

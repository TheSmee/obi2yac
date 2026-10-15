from __future__ import annotations

import tempfile
from pathlib import Path

from obi2yac.config import AppConfig, load_config


def make_config(directory: str | Path, **overrides: object) -> AppConfig:
    root = Path(directory)
    config_path = root / "config.ini"
    config_path.write_text(
        "[network]\n"
        "udp_host = 127.0.0.1\n"
        "udp_port = 5514\n"
        "yac_port = 10629\n"
        "yac_timeout = 0.5\n"
        "[database]\n"
        f"path = {root / 'calls.sqlite3'}\n"
        "[logging]\n"
        "level = DEBUG\n"
        "[pushbullet]\n"
        "enabled = false\n"
        "token = \n"
        "[smtp]\n"
        "enabled = false\n"
        "host = smtp.example.invalid\n"
        "port = 25\n"
        "tls = none\n"
        "username = \n"
        "password = \n"
        "from_name = Test Alert\n"
        "from_address = sender@example.invalid\n"
        "to_address = recipient@example.invalid\n"
        "subject = Test\n"
        "[dtmf]\n"
        "enabled = false\n"
        "trigger_1 = 69#\n"
        "start_marker = DIAL START\n"
        "end_marker = DIAL END\n"
        "digit_marker = DTMF DIGIT\n"
        "on_hook_marker = ON HOOK\n",
        encoding="utf-8",
    )
    env = {
        f"OBI2YAC_{key.upper()}": str(value)
        for key, value in overrides.items()
    }
    return load_config(config_path, env)


class TemporaryDirectoryTestCase:
    def setUp(self) -> None:
        super().setUp()
        self._tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tempdir.cleanup)
        self.temp_path = Path(self._tempdir.name)

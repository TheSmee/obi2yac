from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from obi2yac.config import DEFAULT_DATABASE_PATH, load_config
from obi2yac.tests.helpers import make_config


class ConfigTests(unittest.TestCase):
    def test_config_defaults_and_ini_values(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            config = make_config(temp)

        self.assertEqual(config.udp_host, "127.0.0.1")
        self.assertEqual(config.udp_port, 5514)
        self.assertEqual(config.yac_port, 10629)
        self.assertEqual(config.health_host, "127.0.0.1")
        self.assertEqual(config.health_timeout, 15)
        self.assertFalse(config.ncid_enabled)
        self.assertEqual(config.ncid_host, "")
        self.assertEqual(config.ncid_port, 3333)
        self.assertEqual(config.dtmf_triggers, ("69#",))
        self.assertFalse(config.log_raw_syslog)
        self.assertFalse(config.pushbullet_enabled)
        self.assertFalse(config.smtp_enabled)
        self.assertFalse(config.dtmf_enabled)

    def test_environment_overrides_ini_values(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            config = make_config(temp, network_udp_port=5515, database_path="override.db")

        self.assertEqual(config.udp_port, 5515)
        self.assertEqual(config.database_path, Path("override.db"))

    def test_relative_database_path_in_ini_is_relative_to_config_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            config_path = Path(temp) / "config.ini"
            config_path.write_text(
                "[database]\npath = data/calls.sqlite3\n", encoding="utf-8"
            )
            config = load_config(config_path, environ={})

        self.assertEqual(
            config.database_path, Path(temp) / "data" / "calls.sqlite3"
        )

    def test_environment_only_configuration_needs_no_ini_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            env = {
                "OBI2YAC_UDP_HOST": "127.0.0.1",
                "OBI2YAC_UDP_PORT": "5516",
                "OBI2YAC_DATABASE_PATH": str(Path(temp) / "calls.sqlite3"),
                "OBI2YAC_LOG_LEVEL": "WARNING",
                "OBI2YAC_HEALTH_TIMEOUT": "20",
            }
            with patch("obi2yac.config.Path.is_file", return_value=False):
                config = load_config(environ=env)

        self.assertEqual(config.udp_host, "127.0.0.1")
        self.assertEqual(config.udp_port, 5516)
        self.assertEqual(config.database_path, Path(temp) / "calls.sqlite3")
        self.assertEqual(config.log_level, "WARNING")
        self.assertEqual(config.health_timeout, 20)

    def test_raw_syslog_logging_can_be_enabled_by_environment(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            config = make_config(temp, log_raw_syslog="true")

        self.assertTrue(config.log_raw_syslog)

    def test_health_timeout_can_be_overridden_by_environment(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            config = make_config(temp, health_timeout="20")

        self.assertEqual(config.health_timeout, 20)

    def test_ncid_settings_support_requested_environment_names(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            config_path = Path(temp) / "config.ini"
            config_path.write_text("", encoding="utf-8")
            env = {
                "NCID_ENABLED": "yes",
                "NCID_HOST": "192.0.2.40",
                "NCID_PORT": "3334",
            }
            config = load_config(config_path, environ=env)

        self.assertTrue(config.ncid_enabled)
        self.assertEqual(config.ncid_host, "192.0.2.40")
        self.assertEqual(config.ncid_port, 3334)

    def test_ncid_enabled_requires_host(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaisesRegex(ValueError, "no host is configured"):
                make_config(temp, ncid_enabled="true")

    def test_default_database_is_next_to_python_package(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            env = {}
            with patch("obi2yac.config.Path.is_file", return_value=False):
                config = load_config(environ=env)

        self.assertEqual(config.database_path, DEFAULT_DATABASE_PATH)
        self.assertEqual(config.database_path.parent.name, "data")
        self.assertEqual(config.database_path.parent.parent.name, "obi2yac")

    def test_original_ini_names_have_environment_aliases(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            config = make_config(
                temp,
                syslog_ip="192.0.2.10",
                syslog_port=5517,
                pushbulletlenable="true",
                pushbulletkey="synthetic-token",
            )

        self.assertEqual(config.udp_host, "192.0.2.10")
        self.assertEqual(config.udp_port, 5517)
        self.assertTrue(config.pushbullet_enabled)
        self.assertEqual(config.pushbullet_token, "synthetic-token")

    def test_invalid_port_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaisesRegex(ValueError, "between 1 and 65535"):
                make_config(temp, network_udp_port=70000)

    def test_enabled_pushbullet_requires_token(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaisesRegex(ValueError, "no token is configured"):
                make_config(temp, pushbullet_enabled="true")

    def test_enabled_smtp_requires_delivery_settings(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            config_path = Path(temp) / "config.ini"
            config_path.write_text("[smtp]\nenabled = true\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "SMTP is enabled"):
                load_config(config_path)

    def test_dtmf_requires_trigger_and_smtp(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaisesRegex(ValueError, "no trigger sequence"):
                make_config(
                    temp, dtmf_enabled="true", dtmf_trigger_1=""
                )
            with self.assertRaisesRegex(ValueError, "SMTP is disabled"):
                make_config(temp, dtmf_enabled="true")

    def test_missing_configuration_is_reported(self) -> None:
        with self.assertRaises(FileNotFoundError):
            load_config(Path("does-not-exist.ini"))


if __name__ == "__main__":
    unittest.main()

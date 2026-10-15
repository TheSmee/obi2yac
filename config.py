from __future__ import annotations

import configparser
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping


ENVIRONMENT_ALIASES = {
    "network.udp_host": ("OBI2YAC_UDP_HOST", "OBI2YAC_SYSLOG_IP"),
    "network.udp_port": ("OBI2YAC_UDP_PORT", "OBI2YAC_SYSLOG_PORT"),
    "network.yac_port": ("OBI2YAC_YAC_PORT",),
    "network.yac_timeout": ("OBI2YAC_YAC_TIMEOUT",),
    "database.path": ("OBI2YAC_DATABASE_PATH", "OBI2YAC_DB_PATH"),
    "logging.level": ("OBI2YAC_LOG_LEVEL",),
    "pushbullet.enabled": ("OBI2YAC_PUSHBULLET_ENABLED", "OBI2YAC_PUSHBULLETLENABLE"),
    "pushbullet.token": ("OBI2YAC_PUSHBULLET_TOKEN", "OBI2YAC_PUSHBULLETKEY"),
    "pushbullet.timeout": ("OBI2YAC_PUSHBULLET_TIMEOUT",),
    "smtp.enabled": ("OBI2YAC_SMTP_ENABLED",),
    "smtp.host": ("OBI2YAC_SMTP_HOST", "OBI2YAC_SMTPSERVER"),
    "smtp.port": ("OBI2YAC_SMTP_PORT",),
    "smtp.tls": ("OBI2YAC_SMTP_TLS",),
    "smtp.username": ("OBI2YAC_SMTP_USERNAME",),
    "smtp.password": ("OBI2YAC_SMTP_PASSWORD",),
    "smtp.from_name": ("OBI2YAC_SMTP_FROM_NAME", "OBI2YAC_FROMNAME"),
    "smtp.from_address": ("OBI2YAC_SMTP_FROM_ADDRESS", "OBI2YAC_FROMADDRESS"),
    "smtp.to_address": ("OBI2YAC_SMTP_TO_ADDRESS", "OBI2YAC_TOADDRESS"),
    "smtp.subject": ("OBI2YAC_SMTP_SUBJECT", "OBI2YAC_EMAILSUBJECT"),
    "dtmf.enabled": ("OBI2YAC_DTMF_ENABLED", "OBI2YAC_ENABLEDTMFTRIGGER"),
    "dtmf.trigger_1": ("OBI2YAC_DTMF_TRIGGER_1", "OBI2YAC_DTMFTRIGGER1"),
    "dtmf.trigger_2": ("OBI2YAC_DTMF_TRIGGER_2", "OBI2YAC_DTMFTRIGGER2"),
    "dtmf.trigger_3": ("OBI2YAC_DTMF_TRIGGER_3", "OBI2YAC_DTMFTRIGGER3"),
    "dtmf.start_marker": ("OBI2YAC_DTMF_START_MARKER", "OBI2YAC_DTMFSTART"),
    "dtmf.end_marker": ("OBI2YAC_DTMF_END_MARKER", "OBI2YAC_DTMFEND"),
    "dtmf.digit_marker": ("OBI2YAC_DTMF_DIGIT_MARKER", "OBI2YAC_DTMFKEY"),
    "dtmf.on_hook_marker": ("OBI2YAC_DTMF_ON_HOOK_MARKER", "OBI2YAC_ONHOOK"),
}

DEFAULT_DATABASE_PATH = Path(__file__).resolve().parent / "data" / "obi2yac.sqlite3"


@dataclass(frozen=True)
class AppConfig:
    udp_host: str
    udp_port: int
    yac_port: int
    yac_timeout: float
    database_path: Path
    log_level: str
    pushbullet_enabled: bool
    pushbullet_token: str
    pushbullet_timeout: float
    smtp_enabled: bool
    smtp_host: str
    smtp_port: int
    smtp_tls: str
    smtp_username: str
    smtp_password: str
    smtp_from_name: str
    smtp_from_address: str
    smtp_to_address: str
    email_subject: str
    dtmf_enabled: bool
    dtmf_triggers: tuple[str, ...]
    dtmf_start: str
    dtmf_end: str
    dtmf_key: str
    on_hook: str


def _port(value: str, setting: str) -> int:
    try:
        port = int(value)
    except ValueError as exc:
        raise ValueError(f"{setting} must be an integer port") from exc
    if not 1 <= port <= 65535:
        raise ValueError(f"{setting} must be between 1 and 65535")
    return port


def _positive_float(value: str, setting: str) -> float:
    try:
        result = float(value)
    except ValueError as exc:
        raise ValueError(f"{setting} must be a positive number") from exc
    if result <= 0:
        raise ValueError(f"{setting} must be a positive number")
    return result


def load_config(
    path: str | Path | None = None,
    environ: Mapping[str, str] | None = None,
) -> AppConfig:
    env = os.environ if environ is None else environ
    if path is None:
        configured_path = env.get("OBI2YAC_CONFIG_FILE", "").strip()
        config_path = (
            Path(configured_path)
            if configured_path
            else Path(__file__).resolve().parent / "config.ini"
        )
        if not configured_path and not config_path.is_file():
            working_directory_config = Path("config.ini")
            config_path = (
                working_directory_config
                if working_directory_config.is_file()
                else None
            )
    else:
        config_path = Path(path)
    if config_path is not None and not config_path.is_file():
        raise FileNotFoundError(f"Configuration file not found: {config_path}")

    parser = configparser.ConfigParser(interpolation=None)
    if config_path is not None:
        try:
            with config_path.open("r", encoding="utf-8") as stream:
                parser.read_file(stream)
        except (OSError, configparser.Error) as exc:
            raise ValueError(
                f"Unable to read configuration file {config_path}: {exc}"
            ) from exc

    def get(section: str, option: str, default: str) -> str:
        value = parser.get(section, option, fallback=default)
        env_key = f"OBI2YAC_{section}_{option}".upper()
        for alias in (env_key, *ENVIRONMENT_ALIASES.get(f"{section}.{option}", ())):
            if alias in env:
                return env[alias].strip()
        return value.strip()

    def get_bool(section: str, option: str, default: str = "false") -> bool:
        value = get(section, option, default).lower()
        if value in {"1", "true", "yes", "on"}:
            return True
        if value in {"0", "false", "no", "off"}:
            return False
        raise ValueError(f"[{section}] {option} must be a boolean")

    udp_host = get("network", "udp_host", "0.0.0.0")
    udp_port = _port(get("network", "udp_port", "514"), "network.udp_port")
    yac_port = _port(get("network", "yac_port", "10629"), "network.yac_port")
    yac_timeout = _positive_float(
        get("network", "yac_timeout", "2.0"), "network.yac_timeout"
    )
    database_path_value = get("database", "path", str(DEFAULT_DATABASE_PATH))
    database_path = Path(database_path_value).expanduser()
    database_path_from_environment = any(
        key in env for key in ENVIRONMENT_ALIASES["database.path"]
    )
    if (
        not database_path.is_absolute()
        and config_path is not None
        and not database_path_from_environment
    ):
        database_path = config_path.parent / database_path
    log_level = get("logging", "level", "INFO").upper()
    if log_level not in {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}:
        raise ValueError("[logging] level must be DEBUG, INFO, WARNING, ERROR, or CRITICAL")

    pushbullet_enabled = get_bool("pushbullet", "enabled")
    pushbullet_token = get("pushbullet", "token", "")
    pushbullet_timeout = _positive_float(
        get("pushbullet", "timeout", "5.0"), "pushbullet.timeout"
    )
    if pushbullet_enabled and not pushbullet_token:
        raise ValueError(
            "Pushbullet is enabled but no token is configured; set "
            "[pushbullet] token or OBI2YAC_PUSHBULLET_TOKEN"
        )

    smtp_enabled = get_bool("smtp", "enabled")
    smtp_host = get("smtp", "host", "")
    smtp_port = _port(get("smtp", "port", "25"), "smtp.port")
    smtp_tls = get("smtp", "tls", "none").lower()
    smtp_username = get("smtp", "username", "")
    smtp_password = get("smtp", "password", "")
    smtp_from_name = get("smtp", "from_name", "Obi2Yac Alert")
    smtp_from_address = get("smtp", "from_address", "")
    smtp_to_address = get("smtp", "to_address", "")
    email_subject = get("smtp", "subject", "Alarm Has Been Triggered")
    if smtp_tls not in {"none", "starttls", "ssl"}:
        raise ValueError("[smtp] tls must be none, starttls, or ssl")
    if any(
        "\r" in value or "\n" in value
        for value in (
            smtp_host,
            smtp_from_name,
            smtp_from_address,
            smtp_to_address,
            email_subject,
        )
    ):
        raise ValueError("[smtp] header and host settings must not contain newlines")
    if bool(smtp_username) != bool(smtp_password):
        raise ValueError("[smtp] username and password must be configured together")
    if smtp_enabled and not (smtp_host and smtp_from_address and smtp_to_address):
        raise ValueError(
            "SMTP is enabled but host, from_address, or to_address is missing"
        )

    triggers = tuple(
        trigger
        for trigger in (
            get("dtmf", "trigger_1", ""),
            get("dtmf", "trigger_2", ""),
            get("dtmf", "trigger_3", ""),
        )
        if trigger
    )
    dtmf_enabled = get_bool("dtmf", "enabled")
    if dtmf_enabled and not triggers:
        raise ValueError("DTMF alerts are enabled but no trigger sequence is configured")
    if dtmf_enabled and not smtp_enabled:
        raise ValueError("DTMF alerts are enabled but SMTP is disabled")

    return AppConfig(
        udp_host=udp_host,
        udp_port=udp_port,
        yac_port=yac_port,
        yac_timeout=yac_timeout,
        database_path=database_path,
        log_level=log_level,
        pushbullet_enabled=pushbullet_enabled,
        pushbullet_token=pushbullet_token,
        pushbullet_timeout=pushbullet_timeout,
        smtp_enabled=smtp_enabled,
        smtp_host=smtp_host,
        smtp_port=smtp_port,
        smtp_tls=smtp_tls,
        smtp_username=smtp_username,
        smtp_password=smtp_password,
        smtp_from_name=smtp_from_name,
        smtp_from_address=smtp_from_address,
        smtp_to_address=smtp_to_address,
        email_subject=email_subject,
        dtmf_enabled=dtmf_enabled,
        dtmf_triggers=triggers,
        dtmf_start=get("dtmf", "start_marker", "[CPT] --- FXS h/w tone generator (dial)---"),
        dtmf_end=get(
            "dtmf", "end_marker", "[CPT] --- FXS h/w tone generator (ringback)---"
        ),
        dtmf_key=get(
            "dtmf",
            "digit_marker",
            "[DSP]: ---- H/W DTMF ON (FXS: 0, level:1) :",
        ),
        on_hook=get("dtmf", "on_hook_marker", "[SLIC]:Slic#0 ONHOOK"),
    )

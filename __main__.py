from __future__ import annotations

import argparse
import logging
import sqlite3
import signal
import sys
import threading

from . import __version__
from .config import load_config
from .service import Obi2YacService


class _BelowWarning(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        return record.levelno < logging.WARNING


def configure_logging(level: str) -> None:
    root = logging.getLogger()
    root.setLevel(getattr(logging, level))
    formatter = logging.Formatter(
        "%(asctime)s %(levelname)s %(name)s: %(message)s"
    )
    standard_output = logging.StreamHandler(sys.stdout)
    standard_output.setLevel(logging.DEBUG)
    standard_output.addFilter(_BelowWarning())
    standard_output.setFormatter(formatter)
    standard_error = logging.StreamHandler(sys.stderr)
    standard_error.setLevel(logging.WARNING)
    standard_error.setFormatter(formatter)
    root.handlers.clear()
    root.addHandler(standard_output)
    root.addHandler(standard_error)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the Obi2Yac syslog service")
    parser.add_argument(
        "--config",
        default=None,
        help=(
            "INI configuration path (default: config.ini beside this module, then "
            "config.ini in the working directory, if present)"
        ),
    )
    args = parser.parse_args()

    try:
        config = load_config(args.config)
        configure_logging(config.log_level)
        service = Obi2YacService(config)
    except (FileNotFoundError, ValueError, OSError, sqlite3.Error) as exc:
        logging.basicConfig(level=logging.ERROR, stream=sys.stderr)
        logging.getLogger(__name__).error("%s", exc)
        return 2

    stop_event = threading.Event()

    def request_stop(_signum: int, _frame: object) -> None:
        stop_event.set()

    signal.signal(signal.SIGINT, request_stop)
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, request_stop)

    logging.getLogger(__name__).info(
        "Starting Obi2Yac version %s (UDP %s:%d, database %s)",
        __version__,
        config.udp_host,
        config.udp_port,
        config.database_path,
    )
    try:
        service.serve_until(stop_event)
    except OSError as exc:
        logging.getLogger(__name__).exception("Service failed: %s", exc)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

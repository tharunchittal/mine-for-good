"""Command-line entry point for mine-for-good."""

import argparse
import logging
import sys
from pathlib import Path
from typing import Optional

from mine_for_good import __version__
from mine_for_good.config import configure_interactive, load_config, save_config
from mine_for_good.service import MiningService, PID_FILE, daemonise
from mine_for_good.specs import get_specs, print_specs


def _setup_logging(level: str, log_file: Optional[str] = None) -> None:
    handlers = [logging.StreamHandler(sys.stdout)]
    if log_file:
        Path(log_file).parent.mkdir(parents=True, exist_ok=True)
        handlers.append(logging.FileHandler(log_file, encoding="utf-8"))  # type: ignore[arg-type]

    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=handlers,
    )


def cmd_configure(_args: argparse.Namespace) -> None:
    configure_interactive()
    print("Configuration saved.")


def cmd_specs(_args: argparse.Namespace) -> None:
    print_specs(get_specs())


def cmd_start(args: argparse.Namespace) -> None:
    config = load_config(args.config)
    _setup_logging(
        config["logging"]["level"],
        config["logging"]["file"],
    )

    service = MiningService(config)
    try:
        service.setup()
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)

    if args.daemon:
        print(f"mine-for-good {__version__} starting in background …")
        daemonise(config["logging"]["file"])

    service.run()


def cmd_stop(_args: argparse.Namespace) -> None:
    import os
    import signal as _signal

    if not PID_FILE.exists():
        print("mine-for-good does not appear to be running (no PID file).")
        return

    try:
        pid = int(PID_FILE.read_text().strip())
        os.kill(pid, _signal.SIGTERM)
        print(f"Sent SIGTERM to process {pid}.")
    except (ValueError, ProcessLookupError, PermissionError) as exc:
        print(f"Could not stop mine-for-good: {exc}", file=sys.stderr)


def cmd_status(_args: argparse.Namespace) -> None:
    import os

    if not PID_FILE.exists():
        print("mine-for-good: stopped (no PID file found)")
        return

    try:
        pid = int(PID_FILE.read_text().strip())
        os.kill(pid, 0)  # signal 0 checks existence
        print(f"mine-for-good: running (pid={pid})")
    except ProcessLookupError:
        print("mine-for-good: stopped (stale PID file)")
    except PermissionError:
        print(f"mine-for-good: running (pid={PID_FILE.read_text().strip()}) [no permission to signal]")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="mine-for-good",
        description=(
            "Background Monero CPU miner that automatically pauses when you "
            "use the computer and resumes when you are idle."
        ),
    )
    parser.add_argument(
        "--version", action="version", version=f"%(prog)s {__version__}"
    )

    sub = parser.add_subparsers(dest="command", metavar="COMMAND")
    sub.required = True

    # configure
    p_cfg = sub.add_parser("configure", help="Interactively set wallet address and options")
    p_cfg.set_defaults(func=cmd_configure)

    # specs
    p_specs = sub.add_parser("specs", help="Print system specifications and exit")
    p_specs.set_defaults(func=cmd_specs)

    # start
    p_start = sub.add_parser("start", help="Start the mining service")
    p_start.add_argument(
        "--daemon", "-d",
        action="store_true",
        help="Run in the background (daemonise, POSIX only)",
    )
    p_start.add_argument(
        "--config", "-c",
        default=None,
        metavar="PATH",
        help="Path to a custom config.json file",
    )
    p_start.set_defaults(func=cmd_start)

    # stop
    p_stop = sub.add_parser("stop", help="Stop the background mining service")
    p_stop.set_defaults(func=cmd_stop)

    # status
    p_status = sub.add_parser("status", help="Show whether the service is running")
    p_status.set_defaults(func=cmd_status)

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()

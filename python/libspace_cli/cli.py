from __future__ import annotations

import argparse
import sys

from .commands import cancel_seat_command, discover_command, interfaces_command, login_command, reserve_once_command


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="xauat-libspace-py",
        description="Python CLI for XAUAT libspace seat reservation",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    login_parser = subparsers.add_parser("login", help="Log in with CAS and cache the libspace token")
    login_parser.add_argument("--username", help="CAS username for direct login")
    login_parser.add_argument("--password", help="CAS password for direct login")
    login_parser.add_argument("--url", help="Full final callback URL containing the cas parameter")
    login_parser.add_argument("--cas", help="CAS callback parameter value")
    login_parser.set_defaults(handler=login_command)

    discover_parser = subparsers.add_parser("discover", help="Export bookable rooms and available seat IDs")
    discover_parser.add_argument("--date", help="Target date in YYYY-MM-DD")
    discover_parser.set_defaults(handler=discover_command)

    reserve_parser = subparsers.add_parser("reserve-once", help="Attempt one reservation at the trigger time")
    reserve_parser.add_argument("--force", action="store_true", help="Skip the trigger time window check")
    reserve_parser.set_defaults(handler=reserve_once_command)

    cancel_parser = subparsers.add_parser("cancel-seat", help="Cancel one active seat reservation for the current account")
    cancel_parser.add_argument("--id", help="Reservation id to cancel when multiple active bookings exist")
    cancel_parser.set_defaults(handler=cancel_seat_command)

    interfaces_parser = subparsers.add_parser("interfaces", help="Print or export the observed interface catalog")
    interfaces_parser.add_argument("--format", choices=("json", "md"), help="Output format")
    interfaces_parser.add_argument("--output", help="Write the rendered catalog to a file")
    interfaces_parser.set_defaults(handler=interfaces_command)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    handler = getattr(args, "handler", None)
    if handler is None:
        parser.print_help()
        return 1

    try:
        return int(handler(args) or 0)
    except KeyboardInterrupt:
        print("Operation cancelled.", file=sys.stderr)
        return 130
    except Exception as exc:  # pragma: no cover - protective top-level wrapper
        print(str(exc), file=sys.stderr)
        return 1

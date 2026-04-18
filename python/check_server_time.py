from __future__ import annotations

import argparse
import email.utils
import statistics
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import requests


DEFAULT_BASE_URL = "https://libspace.xauat.edu.cn"


@dataclass
class EndpointCheck:
    name: str
    method: str
    path: str
    json_body: dict | None = None
    extra_headers: dict[str, str] | None = None


ENDPOINTS = [
    EndpointCheck(name="root", method="GET", path="/"),
    EndpointCheck(
        name="config_api",
        method="POST",
        path="/api/index/config",
        json_body={},
        extra_headers={
            "Content-Type": "application/json",
            "X-Requested-With": "XMLHttpRequest",
            "lang": "zh",
        },
    ),
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Check local time against libspace server time via HTTP Date headers."
    )
    parser.add_argument(
        "--base-url",
        default=DEFAULT_BASE_URL,
        help=f"Base URL to check, default: {DEFAULT_BASE_URL}",
    )
    parser.add_argument(
        "--samples",
        type=int,
        default=5,
        help="Number of samples per endpoint, default: 5",
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=0.5,
        help="Seconds to wait between samples, default: 0.5",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=5.0,
        help="HTTP timeout in seconds, default: 5",
    )
    return parser.parse_args()


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def format_dt(dt: datetime) -> str:
    return dt.astimezone().isoformat(timespec="milliseconds")


def timed_request(
    session: requests.Session,
    base_url: str,
    check: EndpointCheck,
    timeout: float,
) -> tuple[requests.Response, datetime, datetime]:
    url = f"{base_url.rstrip('/')}{check.path}"
    headers = dict(check.extra_headers or {})

    started_at = utc_now()
    response = session.request(
        method=check.method,
        url=url,
        json=check.json_body,
        headers=headers,
        timeout=timeout,
    )
    finished_at = utc_now()
    return response, started_at, finished_at


def midpoint(started_at: datetime, finished_at: datetime) -> datetime:
    return started_at + (finished_at - started_at) / 2


def describe_offset(offset_seconds: float) -> str:
    if abs(offset_seconds) < 0.001:
        return "server and local are nearly identical"
    if offset_seconds < 0:
        return f"server is {-offset_seconds:.3f}s behind local"
    return f"server is {offset_seconds:.3f}s ahead of local"


def run_check(
    session: requests.Session,
    base_url: str,
    check: EndpointCheck,
    samples: int,
    interval: float,
    timeout: float,
) -> int:
    print(f"\n=== {check.name} ({check.method} {check.path}) ===")
    offsets: list[float] = []
    errors = 0

    for index in range(1, samples + 1):
        try:
            response, started_at, finished_at = timed_request(
                session=session,
                base_url=base_url,
                check=check,
                timeout=timeout,
            )
            server_date_raw = response.headers.get("Date")
            if not server_date_raw:
                raise RuntimeError("missing Date header")

            server_date = email.utils.parsedate_to_datetime(server_date_raw)
            if server_date.tzinfo is None:
                server_date = server_date.replace(tzinfo=timezone.utc)

            local_midpoint = midpoint(started_at, finished_at)
            offset_seconds = (server_date - local_midpoint).total_seconds()
            rtt_seconds = (finished_at - started_at).total_seconds()
            offsets.append(offset_seconds)

            print(
                f"[{index}/{samples}] "
                f"status={response.status_code} "
                f"local_mid={format_dt(local_midpoint)} "
                f"server_date={format_dt(server_date)} "
                f"offset={offset_seconds:+.3f}s "
                f"rtt={rtt_seconds:.3f}s"
            )
        except Exception as exc:  # noqa: BLE001
            errors += 1
            print(f"[{index}/{samples}] error: {exc}")

        if index != samples:
            time.sleep(interval)

    if not offsets:
        print("No valid samples collected.")
        return errors

    avg_offset = statistics.mean(offsets)
    median_offset = statistics.median(offsets)
    min_offset = min(offsets)
    max_offset = max(offsets)

    print("Summary:")
    print(f"  samples_ok: {len(offsets)}")
    print(f"  samples_failed: {errors}")
    print(f"  avg_offset: {avg_offset:+.3f}s")
    print(f"  median_offset: {median_offset:+.3f}s")
    print(f"  min_offset: {min_offset:+.3f}s")
    print(f"  max_offset: {max_offset:+.3f}s")
    print(f"  verdict: {describe_offset(avg_offset)}")

    return errors


def main() -> int:
    args = parse_args()

    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": "xauat-seminar-time-check/1.0",
        }
    )

    total_errors = 0
    print(f"Base URL: {args.base_url}")
    print(f"Local now: {format_dt(utc_now())}")

    for check in ENDPOINTS:
        total_errors += run_check(
            session=session,
            base_url=args.base_url,
            check=check,
            samples=args.samples,
            interval=args.interval,
            timeout=args.timeout,
        )

    print("\nTip: prefer the dynamic API result when comparing reservation trigger timing.")
    return 1 if total_errors else 0


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


@dataclass(frozen=True)
class ScheduleWindow:
    ok: bool
    reason: str | None
    delay_ms: int
    waited: bool


def _zoned_now(date: datetime | None, time_zone: str) -> datetime:
    tz = _resolve_time_zone(time_zone)
    if date is None:
        return datetime.now(tz=tz)
    if date.tzinfo is None:
        date = date.replace(tzinfo=tz)
    return date.astimezone(tz)


def _resolve_time_zone(time_zone: str):
    try:
        return ZoneInfo(time_zone)
    except ZoneInfoNotFoundError:
        if time_zone == "Asia/Shanghai":
            return timezone(timedelta(hours=8), name="Asia/Shanghai")
        raise


def get_zoned_date_key(date: datetime | None, time_zone: str) -> str:
    return _zoned_now(date, time_zone).strftime("%Y%m%d")


def get_zoned_day_string(date: datetime | None, time_zone: str) -> str:
    return _zoned_now(date, time_zone).strftime("%Y-%m-%d")


def get_zoned_time_string(date: datetime | None, time_zone: str) -> str:
    return _zoned_now(date, time_zone).strftime("%H:%M:%S")


def parse_time_string(value: str) -> int:
    hour, minute, second = (int(part) for part in value.split(":"))
    return hour * 3600 + minute * 60 + second


def sleep_ms(delay_ms: int) -> None:
    time.sleep(delay_ms / 1000)


def enforce_schedule_window(
    *,
    trigger_time: str,
    time_zone: str,
    now: datetime | None = None,
    early_window_seconds: int = 60,
    late_window_seconds: int = 60,
) -> ScheduleWindow:
    current = get_zoned_time_string(now, time_zone)
    now_seconds = parse_time_string(current)
    trigger_seconds = parse_time_string(trigger_time)

    if now_seconds < trigger_seconds - early_window_seconds:
        return ScheduleWindow(ok=False, reason="too_early", delay_ms=0, waited=False)
    if now_seconds > trigger_seconds + late_window_seconds:
        return ScheduleWindow(ok=False, reason="too_late", delay_ms=0, waited=False)
    if now_seconds < trigger_seconds:
        return ScheduleWindow(
            ok=True,
            reason=None,
            delay_ms=(trigger_seconds - now_seconds) * 1000,
            waited=True,
        )
    return ScheduleWindow(ok=True, reason=None, delay_ms=0, waited=False)

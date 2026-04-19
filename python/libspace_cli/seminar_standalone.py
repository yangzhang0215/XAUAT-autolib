from __future__ import annotations

import argparse
import json
from dataclasses import replace
from datetime import datetime, timedelta
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .api import LibraryApi
from .commands import (
    _auth_failure_detail,
    _clear_cached_auth,
    _describe_auth_failure,
    _ensure_authenticated,
    _extract_current_user_card,
    _save_state_payload,
)
from .config import SeminarDefaults, SeminarTarget
from .logger import JsonLogger, create_logger
from .result import is_success_response, is_token_expired_response
from .runtime_paths import RuntimePaths, ensure_runtime_dirs, resolve_named_runtime_paths
from .seminar_service import (
    LIBRARY_CLOSE_TIME,
    build_seminar_group_lookup_time,
    build_seminar_confirm_payload,
    group_seminar_rooms_by_floor,
    normalize_participant_cards,
    resolve_group_members,
    sort_seminar_rooms,
    summarize_seminar_schedule,
    validate_seminar_target,
)
from .seminar_tool_config import SeminarToolConfig, load_seminar_tool_config
from .state import load_state, save_state
from .time_utils import (
    ScheduleWindow,
    enforce_schedule_window,
    get_zoned_day_string,
    get_zoned_time_string,
    parse_time_string,
    resolve_time_zone,
    sleep_ms,
)
from .tree import flatten_seminar_tree


SEMINAR_TOOL_CONFIG_NAME = "seminar.config.local.json"
SEMINAR_TOOL_DISCOVER_STATE_KEY = "lastSeminarToolDiscover"
SEMINAR_TOOL_RESERVE_STATE_KEY = "lastSeminarToolReserve"
TIME_RE = re.compile(r"^\d{2}:\d{2}:\d{2}$")
SHORT_TIME_RE = re.compile(r"^\d{2}:\d{2}$")
EARLY_WINDOW_SECONDS = 60
LATE_WINDOW_SECONDS = 60
MAX_SINGLE_RESERVE_MINUTES = 4 * 60
SECOND_RESERVE_GAP_MINUTES = 15
MIN_FINAL_RESERVE_MINUTES = 60
RESERVATION_SPLIT_ERROR = (
    "Requested seminar time cannot be split into reservation windows with segments up to 4 hours, "
    "15-minute gaps, and a final segment of at least 60 minutes."
)


@dataclass
class SeminarToolContext:
    paths: RuntimePaths
    config: SeminarToolConfig
    state: dict[str, Any]
    logger: JsonLogger
    api: LibraryApi

    def persist_state(self) -> None:
        save_state(self.paths.state_path, self.state)


@dataclass(frozen=True)
class ResolvedReserveOptions:
    day: str
    start_time: str
    end_time: str
    windows: tuple["ReservationWindow", ...]
    room_id: str | None
    participant_cards: list[str]
    defaults: SeminarDefaults
    trigger_time: str
    wait: bool
    force: bool


@dataclass(frozen=True)
class ReservationWindow:
    start_time: str
    end_time: str


def _normalize_optional_string(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _extract_list_payload(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    if isinstance(value, dict):
        for key in ("data", "list", "rows", "items"):
            nested = value.get(key)
            if isinstance(nested, list):
                return nested
    return []


def _extract_day_strings(value: Any) -> list[str]:
    output: list[str] = []
    for item in _extract_list_payload(value):
        if isinstance(item, dict):
            day = _normalize_optional_string(item.get("day") or item.get("date") or item.get("value"))
            if day:
                output.append(day)
            continue
        text = _normalize_optional_string(item)
        if text:
            output.append(text)
    return output


def _build_area_label(room: dict[str, Any]) -> str:
    return " / ".join(
        str(part).strip()
        for part in (room.get("areaName"), room.get("floorName"), room.get("roomName"))
        if str(part or "").strip()
    )


def _write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _validate_short_time(value: str, field_name: str) -> str:
    if SHORT_TIME_RE.match(value) is None:
        raise ValueError(f"{field_name} must be HH:MM")
    hour, minute = (int(part) for part in value.split(":"))
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        raise ValueError(f"{field_name} must be a valid 24-hour time")
    return f"{hour:02d}:{minute:02d}"


def _validate_trigger_time(value: str) -> str:
    if TIME_RE.match(value) is None:
        raise ValueError("Trigger time must be HH:MM:SS")
    return value


def _time_to_minutes(value: str, field_name: str) -> int:
    normalized = _validate_short_time(value, field_name)
    hour, minute = (int(part) for part in normalized.split(":"))
    return hour * 60 + minute


def _minutes_to_time(value: int, field_name: str) -> str:
    if not (0 <= value < 24 * 60):
        raise ValueError(f"{field_name} must stay within the same day")
    hour, minute = divmod(value, 60)
    return f"{hour:02d}:{minute:02d}"


def _reservation_window_capacity(segment_count: int) -> int:
    return segment_count * MAX_SINGLE_RESERVE_MINUTES + (segment_count - 1) * SECOND_RESERVE_GAP_MINUTES


def _minimum_reserved_minutes(segment_count: int) -> int:
    if segment_count <= 0:
        return 0
    return MIN_FINAL_RESERVE_MINUTES + max(0, segment_count - 1)


def _build_segment_durations(total_reserved_minutes: int, segment_count: int) -> tuple[int, ...]:
    if segment_count <= 0:
        raise ValueError(RESERVATION_SPLIT_ERROR)
    if total_reserved_minutes < _minimum_reserved_minutes(segment_count):
        raise ValueError(RESERVATION_SPLIT_ERROR)
    if total_reserved_minutes > segment_count * MAX_SINGLE_RESERVE_MINUTES:
        raise ValueError(RESERVATION_SPLIT_ERROR)

    durations: list[int] = []
    remaining_minutes = total_reserved_minutes
    for index in range(segment_count):
        remaining_segments = segment_count - index
        if remaining_segments == 1:
            duration = remaining_minutes
        else:
            minimum_after_current = _minimum_reserved_minutes(remaining_segments - 1)
            duration = min(MAX_SINGLE_RESERVE_MINUTES, remaining_minutes - minimum_after_current)
        if duration <= 0 or duration > MAX_SINGLE_RESERVE_MINUTES:
            raise ValueError(RESERVATION_SPLIT_ERROR)
        durations.append(duration)
        remaining_minutes -= duration

    if remaining_minutes != 0 or durations[-1] < MIN_FINAL_RESERVE_MINUTES:
        raise ValueError(RESERVATION_SPLIT_ERROR)
    return tuple(durations)


def _build_reservation_windows(start_time: str, end_time: str) -> tuple[ReservationWindow, ...]:
    start_minutes = _time_to_minutes(start_time, "Seminar start time")
    end_minutes = _time_to_minutes(end_time, "Seminar end time")
    if start_minutes >= end_minutes:
        raise ValueError("Seminar end time must be later than seminar start time")
    if end_minutes > _time_to_minutes(LIBRARY_CLOSE_TIME, "Library close time"):
        raise ValueError(f"Seminar end time must be no later than {LIBRARY_CLOSE_TIME}.")

    total_span = end_minutes - start_minutes
    if total_span <= MAX_SINGLE_RESERVE_MINUTES:
        return (ReservationWindow(start_time=start_time, end_time=end_time),)

    segment_count = 2
    while total_span > _reservation_window_capacity(segment_count):
        segment_count += 1

    total_reserved_minutes = total_span - (segment_count - 1) * SECOND_RESERVE_GAP_MINUTES
    durations = _build_segment_durations(total_reserved_minutes, segment_count)

    windows: list[ReservationWindow] = []
    cursor = start_minutes
    for index, duration in enumerate(durations):
        segment_end = cursor + duration
        windows.append(
            ReservationWindow(
                start_time=_minutes_to_time(cursor, f"Reservation segment {index + 1} start time"),
                end_time=_minutes_to_time(segment_end, f"Reservation segment {index + 1} end time"),
            )
        )
        cursor = segment_end + SECOND_RESERVE_GAP_MINUTES

    if _time_to_minutes(windows[-1].end_time, "Reservation final segment end time") != end_minutes:
        raise ValueError(RESERVATION_SPLIT_ERROR)
    return tuple(windows)


def _format_reservation_windows(windows: tuple[ReservationWindow, ...]) -> str:
    return ", ".join(f"{window.start_time}-{window.end_time}" for window in windows)


def _resolve_open_value(value: Any) -> str:
    if value in (None, ""):
        return "1"
    text = str(value).strip().lower()
    if text in {"1", "true", "yes", "on"}:
        return "1"
    if text in {"0", "false", "no", "off"}:
        return "0"
    raise ValueError("Open flag must be 0/1 or true/false")


def _prompt_text(prompt: str, *, default: str | None = None, allow_empty: bool = False) -> str:
    while True:
        suffix = f" [{default}]" if default else ""
        raw = input(f"{prompt}{suffix}: ").strip()
        if raw:
            return raw
        if default is not None:
            return default
        if allow_empty:
            return ""
        print(f"{prompt} is required.")


def _can_prompt() -> bool:
    return bool(getattr(sys.stdin, "isatty", lambda: False)())


def create_seminar_tool_context(command_name: str) -> SeminarToolContext:
    paths = resolve_named_runtime_paths(config_name=SEMINAR_TOOL_CONFIG_NAME)
    ensure_runtime_dirs(paths)
    config = load_seminar_tool_config(paths.config_path)
    state = load_state(paths.state_path)
    logger = create_logger(paths, command_name, time_zone=config.time_zone)
    api = LibraryApi(
        base_url=config.base_url,
        lang=config.lang,
        time_zone=config.time_zone,
        token=state.get("token"),
    )
    return SeminarToolContext(paths=paths, config=config, state=state, logger=logger, api=api)


def _resolve_schedule(
    *,
    trigger_time: str,
    time_zone: str,
    wait: bool,
    now: Any | None = None,
    early_window_seconds: int = EARLY_WINDOW_SECONDS,
    late_window_seconds: int = LATE_WINDOW_SECONDS,
) -> ScheduleWindow:
    if not wait:
        return enforce_schedule_window(
            trigger_time=trigger_time,
            time_zone=time_zone,
            now=now,
            early_window_seconds=early_window_seconds,
            late_window_seconds=late_window_seconds,
        )

    current = parse_time_string(get_zoned_time_string(now, time_zone))
    trigger = parse_time_string(trigger_time)
    if current > trigger + late_window_seconds:
        delay_ms = _delay_until_next_trigger(trigger_time=trigger_time, time_zone=time_zone, now=now)
        return ScheduleWindow(ok=True, reason="rollover", delay_ms=delay_ms, waited=True)
    if current < trigger:
        return ScheduleWindow(ok=True, reason=None, delay_ms=(trigger - current) * 1000, waited=True)
    return ScheduleWindow(ok=True, reason=None, delay_ms=0, waited=False)


def _delay_until_next_trigger(*, trigger_time: str, time_zone: str, now: datetime | None) -> int:
    tz = resolve_time_zone(time_zone)
    current = datetime.now(tz) if now is None else (now.astimezone(tz) if now.tzinfo else now.replace(tzinfo=tz))
    trigger_seconds = parse_time_string(trigger_time)
    trigger_hour, remainder = divmod(trigger_seconds, 3600)
    trigger_minute, trigger_second = divmod(remainder, 60)
    next_day = current.date() + timedelta(days=1)
    target = datetime(
        next_day.year,
        next_day.month,
        next_day.day,
        trigger_hour,
        trigger_minute,
        trigger_second,
        tzinfo=tz,
    )
    return max(0, int((target - current).total_seconds() * 1000))


def _next_day_string(*, time_zone: str, now: datetime | None) -> str:
    tz = resolve_time_zone(time_zone)
    current = datetime.now(tz) if now is None else (now.astimezone(tz) if now.tzinfo else now.replace(tzinfo=tz))
    return (current.date() + timedelta(days=1)).strftime("%Y-%m-%d")


def _resolve_defaults(ctx: SeminarToolContext, args: Any, *, allow_prompt: bool) -> SeminarDefaults:
    base = ctx.config.seminar.defaults

    title = _normalize_optional_string(base.title) or _normalize_optional_string(getattr(args, "title", None))
    if not title and allow_prompt:
        title = _prompt_text("Seminar title")
    if not title:
        raise ValueError("Seminar title is required")

    content = _normalize_optional_string(base.content) or _normalize_optional_string(getattr(args, "content", None))
    if not content and allow_prompt:
        content = _prompt_text("Seminar content")
    if not content:
        raise ValueError("Seminar content is required")

    mobile = _normalize_optional_string(base.mobile) or _normalize_optional_string(getattr(args, "mobile", None))
    if not mobile and allow_prompt:
        mobile = _prompt_text("Mobile number")
    if not mobile:
        raise ValueError("Seminar mobile is required")

    open_source = _normalize_optional_string(base.open)
    if open_source is None:
        open_source = _normalize_optional_string(getattr(args, "open", None))
    open_value = _resolve_open_value(open_source or "1")
    return SeminarDefaults(title=title, content=content, mobile=mobile, open=open_value)


def _resolve_participants(ctx: SeminarToolContext, args: Any, *, allow_prompt: bool) -> list[str]:
    participants = normalize_participant_cards(getattr(ctx.config.seminar, "participants", None))
    if participants:
        return participants

    participants = normalize_participant_cards(getattr(args, "participant", None))
    if participants or not allow_prompt:
        return participants

    raw = _prompt_text(
        "Additional participant student IDs, comma separated (blank for none)",
        allow_empty=True,
    )
    if not raw:
        return []
    return normalize_participant_cards([item.strip() for item in raw.split(",")])


def _resolve_reserve_options(ctx: SeminarToolContext, args: Any, *, allow_prompt: bool) -> ResolvedReserveOptions:
    default_day = get_zoned_day_string(None, ctx.config.time_zone)
    day = _normalize_optional_string(getattr(args, "date", None))
    day = day or default_day
    if day != default_day:
        raise ValueError(f"Standalone seminar reservations only support the current day ({default_day}).")

    start_time = _normalize_optional_string(getattr(ctx.config.seminar, "start_time", None))
    if start_time is None:
        start_time = _normalize_optional_string(getattr(args, "start", None))
    if allow_prompt and not start_time:
        start_time = _prompt_text("Start time (HH:MM)")
    if not start_time:
        raise ValueError("Seminar start time is required")
    start_time = _validate_short_time(start_time, "Seminar start time")

    end_time = _normalize_optional_string(getattr(ctx.config.seminar, "end_time", None))
    if end_time is None:
        end_time = _normalize_optional_string(getattr(args, "end", None))
    if allow_prompt and not end_time:
        end_time = _prompt_text("End time (HH:MM)")
    if not end_time:
        raise ValueError("Seminar end time is required")
    end_time = _validate_short_time(end_time, "Seminar end time")
    windows = _build_reservation_windows(start_time, end_time)

    room_id = None
    if not ctx.config.seminar.priority_room_ids:
        room_id = _normalize_optional_string(getattr(args, "room_id", None))
        if allow_prompt:
            room_id = room_id or _prompt_text("Room ID")
        elif not room_id:
            raise ValueError("config.seminar.priorityRoomIds is empty, so --room-id is required.")

    trigger_time = _normalize_optional_string(getattr(ctx.config.seminar, "trigger_time", None))
    if trigger_time is None:
        trigger_time = _normalize_optional_string(getattr(args, "trigger_time", None))
    trigger_time = trigger_time or "08:00:00"
    trigger_time = _validate_trigger_time(trigger_time)

    return ResolvedReserveOptions(
        day=day,
        start_time=start_time,
        end_time=end_time,
        windows=windows,
        room_id=room_id,
        participant_cards=_resolve_participants(ctx, args, allow_prompt=allow_prompt),
        defaults=_resolve_defaults(ctx, args, allow_prompt=allow_prompt),
        trigger_time=trigger_time,
        wait=bool(getattr(args, "wait", False)),
        force=bool(getattr(args, "force", False)),
    )


def _get_room_maps(ctx: SeminarToolContext, target_day: str) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    tree_response = ctx.api.get_seminar_tree(date=target_day)
    if not is_success_response(tree_response):
        raise RuntimeError(tree_response.get("msg", "Failed to fetch the seminar room tree"))

    all_rooms = flatten_seminar_tree(tree_response.get("data"))
    room_lookup = {str(room.get("roomId")): room for room in all_rooms}
    valid_lookup = {
        str(room.get("roomId")): room
        for room in all_rooms
        if int(room.get("isValid", 1) or 0) == 1
    }
    return room_lookup, valid_lookup


def _build_target(
    room: dict[str, Any],
    *,
    day: str,
    start_time: str,
    end_time: str,
) -> SeminarTarget:
    return SeminarTarget(
        label=_build_area_label(room),
        area_id=room["areaId"],
        room_id=room["roomId"],
        day=day,
        start_time=start_time,
        end_time=end_time,
    )


def _candidate_summary(
    room: dict[str, Any],
    request: ResolvedReserveOptions,
    *,
    start_time: str | None = None,
    end_time: str | None = None,
) -> dict[str, Any]:
    target = _build_target(
        room,
        day=request.day,
        start_time=start_time or request.start_time,
        end_time=end_time or request.end_time,
    )
    return {
        "label": target.label,
        "areaId": target.area_id,
        "roomId": target.room_id,
        "day": target.day,
        "startTime": target.start_time,
        "endTime": target.end_time,
    }


def _build_skip_record(
    *,
    room: dict[str, Any] | None,
    request: ResolvedReserveOptions,
    reason: str,
    detail: str,
    response: dict[str, Any] | None = None,
    summary: dict[str, Any] | None = None,
    start_time: str | None = None,
    end_time: str | None = None,
    submitted_reservations: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    record: dict[str, Any] = {
        "reason": reason,
        "detail": detail,
    }
    if room is not None:
        record["target"] = _candidate_summary(room, request, start_time=start_time, end_time=end_time)
    if response is not None:
        record["response"] = response
    if summary is not None:
        record["summary"] = summary
    if submitted_reservations:
        record["submittedReservations"] = submitted_reservations
    return record


def _resolve_candidate_rooms(
    *,
    room_lookup: dict[str, dict[str, Any]],
    valid_lookup: dict[str, dict[str, Any]],
    request: ResolvedReserveOptions,
    priority_room_ids: list[Any],
) -> tuple[bool, list[dict[str, Any]], list[dict[str, Any]]]:
    if request.room_id:
        room = room_lookup.get(str(request.room_id))
        if room is None:
            return True, [], [
                _build_skip_record(
                    room=None,
                    request=request,
                    reason="room_not_found",
                    detail=f"Room {request.room_id} was not found in the seminar tree for {request.day}.",
                )
            ]
        if str(request.room_id) not in valid_lookup:
            return True, [], [
                _build_skip_record(
                    room=room,
                    request=request,
                    reason="room_invalid",
                    detail=f"Room {request.room_id} is not valid for {request.day}.",
                )
            ]
        return True, [valid_lookup[str(request.room_id)]], []

    seen: set[str] = set()
    candidates: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    for room_id in priority_room_ids:
        key = str(room_id)
        if key in seen:
            continue
        seen.add(key)

        room = room_lookup.get(key)
        if room is None:
            skipped.append(
                _build_skip_record(
                    room=None,
                    request=request,
                    reason="room_not_found",
                    detail=f"Priority room {room_id} was not found in the seminar tree for {request.day}.",
                )
            )
            continue

        valid_room = valid_lookup.get(key)
        if valid_room is None:
            skipped.append(
                _build_skip_record(
                    room=room,
                    request=request,
                    reason="room_invalid",
                    detail=f"Priority room {room_id} is not valid for {request.day}.",
                )
            )
            continue

        candidates.append(valid_room)

    return False, candidates, skipped


def _check_room_available_on_day(ctx: SeminarToolContext, room: dict[str, Any], request: ResolvedReserveOptions) -> tuple[bool, dict[str, Any] | None]:
    response = ctx.api.get_seminar_date({"build_id": room["roomId"]})
    if not is_success_response(response):
        return False, _build_skip_record(
            room=room,
            request=request,
            reason="date_query_failed",
            detail=response.get("msg", "Failed to query the room date list."),
            response=response,
        )

    available_days = _extract_day_strings(response.get("data"))
    # Some current seminar rooms return an empty date list even though the same-day
    # schedule/details and the final reservation flow are valid. Treat an empty
    # date-list response as inconclusive instead of blocking the reservation early.
    if available_days and request.day not in available_days:
        return False, _build_skip_record(
            room=room,
            request=request,
            reason="day_unavailable",
            detail=f"Room {room['roomId']} is not bookable on {request.day}.",
            summary={"availableDays": available_days},
        )

    return True, None


def _attempt_reservation_for_room(
    *,
    ctx: SeminarToolContext,
    room: dict[str, Any],
    request: ResolvedReserveOptions,
    organizer_card: str | None,
) -> tuple[bool, dict[str, Any]]:
    day_ok, day_failure = _check_room_available_on_day(ctx, room, request)
    if not day_ok and day_failure is not None:
        return False, day_failure

    detail_response = ctx.api.get_seminar_detail(room_id=room["roomId"])
    if not is_success_response(detail_response):
        return False, _build_skip_record(
            room=room,
            request=request,
            reason="detail_query_failed",
            detail=detail_response.get("msg", "Failed to query room detail."),
            response=detail_response,
        )
    detail_data = detail_response.get("data") if isinstance(detail_response.get("data"), dict) else {}

    schedule_response = ctx.api.get_seminar_schedule(
        room_id=room["roomId"],
        area_id=room["areaId"],
        day=request.day,
    )
    if not is_success_response(schedule_response):
        return False, _build_skip_record(
            room=room,
            request=request,
            reason="schedule_query_failed",
            detail=schedule_response.get("msg", "Failed to query room schedule."),
            response=schedule_response,
        )
    schedule_data = schedule_response.get("data") if isinstance(schedule_response.get("data"), dict) else {}

    lookup_window = request.windows[0]
    participants_result = resolve_group_members(
        api=ctx.api,
        participant_cards=request.participant_cards,
        organizer_card=organizer_card,
        lookup_room_id=room["roomId"],
        lookup_begin_time=build_seminar_group_lookup_time(day=request.day, time_text=lookup_window.start_time),
        lookup_end_time=build_seminar_group_lookup_time(day=request.day, time_text=lookup_window.end_time),
    )
    if not participants_result["ok"]:
        failure = _build_skip_record(
            room=room,
            request=request,
            reason=str(participants_result.get("reason") or "group_lookup_failed"),
            detail=str(participants_result.get("detail") or "Failed to resolve participants."),
            response=participants_result.get("response"),
            start_time=lookup_window.start_time,
            end_time=lookup_window.end_time,
        )
        if participants_result.get("card"):
            failure["card"] = participants_result.get("card")
        return False, failure
    participants = participants_result["participants"]

    for window in request.windows:
        target = _build_target(
            room,
            day=request.day,
            start_time=window.start_time,
            end_time=window.end_time,
        )
        validation = validate_seminar_target(
            target=target,
            schedule_data=schedule_data,
            detail_data=detail_data,
            participant_count=len(participants.member_ids),
            time_zone=ctx.config.time_zone,
        )
        if not validation["ok"]:
            return False, _build_skip_record(
                room=room,
                request=request,
                reason=str(validation["reason"]),
                detail=str(validation["detail"]),
                summary=validation.get("summary"),
                start_time=window.start_time,
                end_time=window.end_time,
            )

    submitted_reservations: list[dict[str, Any]] = []
    for index, window in enumerate(request.windows):
        target = _build_target(
            room,
            day=request.day,
            start_time=window.start_time,
            end_time=window.end_time,
        )
        payload = build_seminar_confirm_payload(
            target=target,
            defaults=request.defaults,
            teamusers=participants.teamusers,
        )
        submit_response = ctx.api.confirm_seminar_reservation(payload)
        retried_after_auth_refresh = False
        if not is_success_response(submit_response) and is_token_expired_response(submit_response):
            retried_after_auth_refresh = True
            ctx.logger.warn(
                "Standalone seminar segment submit hit expired token; retrying current segment after re-authentication",
                {
                    "roomId": room["roomId"],
                    "segmentIndex": index + 1,
                    "startTime": window.start_time,
                    "endTime": window.end_time,
                },
            )
            _clear_cached_auth(ctx)
            auth_result = _ensure_authenticated(ctx)
            if not auth_result["ok"]:
                return False, _build_skip_record(
                    room=room,
                    request=request,
                    reason="submit_failed",
                    detail=(
                        "Seminar reservation submission failed after token expiry because automatic "
                        f"re-login did not succeed: {_describe_auth_failure(auth_result)}"
                    ),
                    response=submit_response,
                    summary={"reAuth": _auth_failure_detail(auth_result)},
                    start_time=window.start_time,
                    end_time=window.end_time,
                    submitted_reservations=submitted_reservations,
                )
            submit_response = ctx.api.confirm_seminar_reservation(payload)
        if not is_success_response(submit_response):
            detail = submit_response.get("msg", "Seminar reservation submission failed.")
            if retried_after_auth_refresh:
                detail = f"Seminar reservation submission still failed after automatic re-login retry: {detail}"
            return False, _build_skip_record(
                room=room,
                request=request,
                reason="submit_failed",
                detail=detail,
                response=submit_response,
                summary={"retriedAfterTokenExpired": retried_after_auth_refresh} if retried_after_auth_refresh else None,
                start_time=window.start_time,
                end_time=window.end_time,
                submitted_reservations=submitted_reservations,
            )

        submitted_reservations.append(
            {
                "target": _candidate_summary(
                    room,
                    request,
                    start_time=window.start_time,
                    end_time=window.end_time,
                ),
                "response": submit_response,
            }
        )

    return True, {"participants": participants, "reservations": submitted_reservations}


def _build_reserve_success_detail(
    *,
    room: dict[str, Any],
    request: ResolvedReserveOptions,
    participant_cards: list[str],
    participant_ids: list[str],
    teamusers: str,
    reservations: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "requestedWindow": {
            "day": request.day,
            "startTime": request.start_time,
            "endTime": request.end_time,
        },
        "reservations": reservations,
        "participantCards": participant_cards,
        "participantIds": participant_ids,
        "teamusers": teamusers,
    }


def _format_blocked_ranges_text(value: Any) -> str:
    if not isinstance(value, list) or not value:
        return "无"

    ranges: list[str] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        start_time = _normalize_optional_string(item.get("startTime"))
        end_time = _normalize_optional_string(item.get("endTime"))
        if start_time and end_time:
            ranges.append(f"{start_time}-{end_time}")
    return "、".join(ranges) if ranges else "无"


def _build_discover_text_summary(payload: dict[str, Any]) -> str:
    lines: list[str] = []
    target_date = _normalize_optional_string(payload.get("targetDate")) or "-"
    generated_at = _normalize_optional_string(payload.get("generatedAt")) or "-"
    rooms = payload.get("rooms") if isinstance(payload.get("rooms"), list) else []

    lines.append("独立研讨室今日空闲摘要")
    lines.append(f"生成时间：{generated_at}")
    lines.append(f"目标日期：{target_date}")
    lines.append(f"房间数量：{len(rooms)}")
    lines.append("")

    if not rooms:
        lines.append("未发现可用研讨室。")
        return "\n".join(lines)

    for index, room in enumerate(rooms, start=1):
        label = _normalize_optional_string(room.get("label")) or f"roomId {room.get('roomId')}"
        room_id = room.get("roomId")
        upload_required = "是" if room.get("uploadRequired") else "否"
        member_count = _normalize_optional_string(room.get("memberCount")) or "-"
        daily = room.get("dailyAvailability") if isinstance(room.get("dailyAvailability"), dict) else {}
        start_time = _normalize_optional_string(daily.get("startTime")) or "-"
        end_time = _normalize_optional_string(daily.get("endTime")) or "-"
        min_person = _normalize_optional_string(daily.get("minPerson")) or "-"
        max_person = _normalize_optional_string(daily.get("maxPerson")) or "-"
        available_days = room.get("availableDays") if isinstance(room.get("availableDays"), list) else []
        available_text = "、".join(str(item) for item in available_days if str(item).strip()) or "-"

        lines.append(f"{index}. {label}")
        lines.append(f"   roomId：{room_id}")
        lines.append(f"   开放时间：{start_time}-{end_time}（最晚不超过 {LIBRARY_CLOSE_TIME}）")
        lines.append(f"   人数范围：{min_person}-{max_person}")
        lines.append(f"   房间容量：{member_count}")
        lines.append(f"   需要上传材料：{upload_required}")
        lines.append(f"   禁用时段：{_format_blocked_ranges_text(daily.get('blockedRanges'))}")
        lines.append(f"   可预约日期：{available_text}")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def discover_command(args: Any) -> int:
    ctx = create_seminar_tool_context("seminar-tool-discover")
    requested_date = _normalize_optional_string(getattr(args, "date", None))
    target_date = requested_date or get_zoned_day_string(None, ctx.config.time_zone)
    include_daily_detail = True
    ctx.logger.info(
        "Starting standalone seminar discover flow",
        {"targetDate": target_date, "includeDailyDetail": include_daily_detail},
    )

    auth_result = _ensure_authenticated(ctx)
    if not auth_result["ok"]:
        detail = _auth_failure_detail(auth_result)
        _save_state_payload(ctx, SEMINAR_TOOL_DISCOVER_STATE_KEY, "api_error", detail)
        ctx.logger.error("Authentication failed during standalone seminar discover", detail)
        print(_describe_auth_failure(auth_result))
        return 1

    tree_response = ctx.api.get_seminar_tree(date=target_date)
    if not is_success_response(tree_response):
        detail = {"reason": "tree_query_failed", "response": tree_response}
        _save_state_payload(ctx, SEMINAR_TOOL_DISCOVER_STATE_KEY, "api_error", detail)
        ctx.logger.error("Failed to fetch seminar tree", detail)
        print(tree_response.get("msg", "Failed to fetch the seminar room tree"))
        return 1

    output: dict[str, Any] = {
        "generatedAt": f"{get_zoned_day_string(None, ctx.config.time_zone)}T{get_zoned_time_string(None, ctx.config.time_zone)}",
        "targetDate": target_date,
        "rooms": [],
        "targetTemplate": [],
        "roomDetail": {},
    }

    rooms = sort_seminar_rooms(
        [room for room in flatten_seminar_tree(tree_response.get("data")) if int(room.get("isValid", 1) or 0) == 1]
    )
    for room in rooms:
        room_label = _build_area_label(room)
        detail_response = ctx.api.get_seminar_detail(room_id=room["roomId"])
        detail_data = detail_response.get("data") if is_success_response(detail_response) and isinstance(detail_response.get("data"), dict) else {}
        if detail_data:
            output["roomDetail"][str(room["roomId"])] = detail_data

        room_date_response = ctx.api.get_seminar_date({"build_id": room["roomId"]})
        available_days = _extract_day_strings(room_date_response.get("data")) if is_success_response(room_date_response) else []

        room_record: dict[str, Any] = {
            **room,
            "label": room_label,
            "availableDays": available_days,
            "uploadRequired": bool(int(str(detail_data.get("upload", 0) or 0))),
            "memberCount": detail_data.get("membercount"),
        }

        if include_daily_detail:
            schedule_response = ctx.api.get_seminar_schedule(
                room_id=room["roomId"],
                area_id=room["areaId"],
                day=target_date,
            )
            if is_success_response(schedule_response):
                schedule_data = schedule_response.get("data") if isinstance(schedule_response.get("data"), dict) else {}
                summary = summarize_seminar_schedule(
                    schedule_data=schedule_data,
                    detail_data=detail_data,
                    time_zone=ctx.config.time_zone,
                )
                room_record["dailyAvailability"] = {
                    "startTime": summary.get("startTime"),
                    "endTime": summary.get("endTime"),
                    "minPerson": summary.get("minPerson"),
                    "maxPerson": summary.get("maxPerson"),
                    "minTime": summary.get("minTime"),
                    "maxTime": summary.get("maxTime"),
                    "blockedRanges": summary.get("blockedRanges"),
                    "uploadRequired": summary.get("uploadRequired"),
                }
                if summary.get("startTime") and summary.get("endTime"):
                    output["targetTemplate"].append(
                        {
                            "label": room_label,
                            "areaId": room["areaId"],
                            "roomId": room["roomId"],
                            "day": target_date,
                            "startTime": summary["startTime"],
                            "endTime": summary["endTime"],
                        }
                    )
            else:
                room_record["dailyAvailabilityError"] = schedule_response.get("msg", "Failed to fetch seminar daily schedule")

        output["rooms"].append(room_record)

    output["rooms"] = sort_seminar_rooms(output["rooms"])
    output["floorGroups"] = [
        {
            "floorName": floor_name,
            "roomCount": len(floor_rooms),
            "roomIds": [room.get("roomId") for room in floor_rooms],
        }
        for floor_name, floor_rooms in group_seminar_rooms_by_floor(output["rooms"])
    ]

    output_path = ctx.paths.runtime_dir / f"seminar-tool-discover-{target_date.replace('-', '')}.json"
    txt_output_path = ctx.paths.runtime_dir / f"seminar-tool-discover-{target_date.replace('-', '')}.txt"
    _write_json(output_path, output)
    _write_text(txt_output_path, _build_discover_text_summary(output))
    _save_state_payload(
        ctx,
        SEMINAR_TOOL_DISCOVER_STATE_KEY,
        "success",
        {
            "targetDate": target_date,
            "outputPath": str(output_path),
            "textOutputPath": str(txt_output_path),
            "roomCount": len(output["rooms"]),
        },
    )
    ctx.logger.info(
        "Standalone seminar discover result written",
        {"filePath": str(output_path), "textFilePath": str(txt_output_path), "roomCount": len(output["rooms"])},
    )

    print(f"Wrote standalone seminar discover result to: {output_path}")
    print(f"Wrote standalone seminar discover text summary to: {txt_output_path}")
    print(f"Seminar rooms: {len(output['rooms'])}")
    return 0


def reserve_command(args: Any) -> int:
    ctx = create_seminar_tool_context("seminar-tool-reserve")
    allow_prompt = _can_prompt()

    try:
        request = _resolve_reserve_options(ctx, args, allow_prompt=allow_prompt)
    except ValueError as exc:
        detail = {"reason": "invalid_arguments", "message": str(exc)}
        _save_state_payload(ctx, SEMINAR_TOOL_RESERVE_STATE_KEY, "api_error", detail)
        ctx.logger.error("Invalid standalone seminar reserve arguments", detail)
        print(str(exc))
        return 1

    ctx.logger.info(
        "Starting standalone seminar reserve flow",
        {
            "day": request.day,
            "startTime": request.start_time,
            "endTime": request.end_time,
            "windows": [window.__dict__ for window in request.windows],
            "roomId": request.room_id,
            "participantCount": len(request.participant_cards),
            "wait": request.wait,
            "force": request.force,
        },
    )

    if not request.force:
        schedule = _resolve_schedule(
            trigger_time=request.trigger_time,
            time_zone=ctx.config.time_zone,
            wait=request.wait,
        )
        if not schedule.ok:
            detail = {"reason": schedule.reason, "triggerTime": request.trigger_time, "wait": request.wait}
            _save_state_payload(ctx, SEMINAR_TOOL_RESERVE_STATE_KEY, "schedule_miss", detail)
            ctx.logger.warn("Standalone seminar execution skipped because schedule window was missed", detail)
            print(f"Execution skipped: {schedule.reason}")
            return 1
        if schedule.reason == "rollover":
            next_day = _next_day_string(time_zone=ctx.config.time_zone, now=None)
            request = replace(request, day=next_day)
            ctx.logger.info(
                "Standalone seminar schedule rolled over to next day",
                {"triggerTime": request.trigger_time, "nextDay": next_day, "delayMs": schedule.delay_ms},
            )
        if schedule.delay_ms > 0:
            ctx.logger.info("Waiting until standalone seminar trigger time", {"delayMs": schedule.delay_ms})
            sleep_ms(schedule.delay_ms)

    auth_result = _ensure_authenticated(ctx)
    if not auth_result["ok"]:
        detail = _auth_failure_detail(auth_result)
        _save_state_payload(ctx, SEMINAR_TOOL_RESERVE_STATE_KEY, "api_error", detail)
        ctx.logger.error("Authentication failed during standalone seminar reserve", detail)
        print(_describe_auth_failure(auth_result))
        return 1

    organizer_card = _extract_current_user_card(ctx, auth_result.get("myInfo"))

    try:
        room_lookup, valid_lookup = _get_room_maps(ctx, request.day)
    except RuntimeError as exc:
        detail = {"reason": "tree_query_failed", "message": str(exc)}
        _save_state_payload(ctx, SEMINAR_TOOL_RESERVE_STATE_KEY, "api_error", detail)
        ctx.logger.error("Failed to fetch seminar room tree for standalone reserve", detail)
        print(str(exc))
        return 1

    explicit_room, candidate_rooms, skipped_rooms = _resolve_candidate_rooms(
        room_lookup=room_lookup,
        valid_lookup=valid_lookup,
        request=request,
        priority_room_ids=ctx.config.seminar.priority_room_ids,
    )
    if not candidate_rooms:
        detail = {
            "reason": "no_candidate_room",
            "skippedRooms": skipped_rooms,
        }
        _save_state_payload(ctx, SEMINAR_TOOL_RESERVE_STATE_KEY, "no_available_target", detail)
        ctx.logger.warn("No standalone seminar room candidate is available", detail)
        print(skipped_rooms[0]["detail"] if explicit_room and skipped_rooms else "No candidate seminar room is available.")
        return 1

    for room in candidate_rooms:
        success, result = _attempt_reservation_for_room(
            ctx=ctx,
            room=room,
            request=request,
            organizer_card=organizer_card,
        )
        if success:
            participants = result["participants"]
            success_detail = _build_reserve_success_detail(
                room=room,
                request=request,
                participant_cards=participants.cards,
                participant_ids=participants.member_ids,
                teamusers=participants.teamusers,
                reservations=result["reservations"],
            )
            _save_state_payload(ctx, SEMINAR_TOOL_RESERVE_STATE_KEY, "success", success_detail)
            ctx.logger.info("Standalone seminar reservation succeeded", success_detail)
            print(
                f"Seminar reservation succeeded: roomId={room['roomId']}, "
                f"day={request.day}, windows={_format_reservation_windows(request.windows)}"
            )
            return 0

        skipped_rooms.append(result)
        if result.get("submittedReservations"):
            detail = {
                "reason": result["reason"],
                "message": result["detail"],
                "target": result.get("target"),
                "summary": result.get("summary"),
                "response": result.get("response"),
                "submittedReservations": result.get("submittedReservations"),
            }
            _save_state_payload(ctx, SEMINAR_TOOL_RESERVE_STATE_KEY, "partial_success", detail)
            ctx.logger.error("Standalone seminar reservation partially succeeded", detail)
            print(
                "A reservation segment was submitted successfully, but a later segment failed. "
                f"Submitted windows: {', '.join(item['target']['startTime'] + '-' + item['target']['endTime'] for item in result['submittedReservations'])}. "
                f"Failure: {result['detail']}"
            )
            return 1
        if explicit_room:
            detail = {
                "reason": result["reason"],
                "message": result["detail"],
                "card": result.get("card"),
                "target": result.get("target"),
                "summary": result.get("summary"),
                "response": result.get("response"),
            }
            _save_state_payload(ctx, SEMINAR_TOOL_RESERVE_STATE_KEY, "api_error", detail)
            ctx.logger.error("Standalone seminar reservation failed for explicit room", detail)
            print(result["detail"])
            return 1

        ctx.logger.warn("Skipping priority seminar room after reservation attempt", result)

    participant_failure = next(
        (
            item
            for item in skipped_rooms
            if item.get("reason") in {"group_lookup_failed", "group_lookup_invalid", "self_in_participants"}
        ),
        None,
    )
    if participant_failure is not None:
        detail = {
            "reason": participant_failure["reason"],
            "message": participant_failure["detail"],
            "card": participant_failure.get("card"),
            "target": participant_failure.get("target"),
            "response": participant_failure.get("response"),
        }
        _save_state_payload(ctx, SEMINAR_TOOL_RESERVE_STATE_KEY, "api_error", detail)
        ctx.logger.error("Failed to resolve seminar participants for standalone reserve", detail)
        print(participant_failure["detail"])
        return 1

    detail = {
        "reason": "no_room_submitted",
        "skippedRooms": skipped_rooms,
    }
    _save_state_payload(ctx, SEMINAR_TOOL_RESERVE_STATE_KEY, "no_available_target", detail)
    ctx.logger.warn("No standalone seminar room could be submitted", detail)
    print("No seminar room could be reserved.")
    return 1


def _add_shared_reserve_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--date", help="Target date in YYYY-MM-DD; only the current day is supported")
    parser.add_argument("--start", help="Target start time in HH:MM; used when config.seminar.startTime is empty")
    parser.add_argument("--end", help="Target end time in HH:MM; used when config.seminar.endTime is empty")
    parser.add_argument("--mobile", help="Contact mobile number; used when config.seminar.defaults.mobile is empty")
    parser.add_argument("--participant", action="append", default=[], help="One additional participant student ID")
    parser.add_argument("--room-id", help="Explicit room id; used only when config.seminar.priorityRoomIds is empty")
    parser.add_argument("--title", help="Seminar request title; used when config.seminar.defaults.title is empty")
    parser.add_argument("--content", help="Seminar request content; used when config.seminar.defaults.content is empty")
    parser.add_argument("--open", choices=("0", "1"), help="Whether the reservation is public; used when config.seminar.defaults.open is empty")
    parser.add_argument("--trigger-time", help="Trigger time in HH:MM:SS; used when config.seminar.triggerTime is empty")
    parser.add_argument("--wait", action="store_true", help="Wait until trigger time even when launched early")
    parser.add_argument("--force", action="store_true", help="Skip trigger time checks")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="xauat-seminar-tool",
        description="Standalone seminar-room reservation tool for XAUAT libspace",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    discover_parser = subparsers.add_parser("discover", help="Export seminar-room candidates and availability details")
    discover_parser.add_argument("--date", help="Target date in YYYY-MM-DD")
    discover_parser.set_defaults(handler=discover_command)

    reserve_parser = subparsers.add_parser("reserve", help="Reserve one seminar room through the standalone tool")
    _add_shared_reserve_arguments(reserve_parser)
    reserve_parser.set_defaults(handler=reserve_command)

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

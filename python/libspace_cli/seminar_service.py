from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from .config import SeminarDefaults, SeminarTarget
from .result import is_success_response
from .time_utils import resolve_time_zone

LIBRARY_CLOSE_TIME = "22:30"
LIBRARY_CLOSE_MINUTES = 22 * 60 + 30
_FLOOR_DIGIT_RE = re.compile(r"(\d+)")
_CHINESE_FLOOR_DIGITS = {
    "一": 1,
    "二": 2,
    "三": 3,
    "四": 4,
    "五": 5,
    "六": 6,
    "七": 7,
    "八": 8,
    "九": 9,
    "十": 10,
}


@dataclass(frozen=True)
class SeminarResolvedParticipants:
    members: list[dict[str, Any]]
    teamusers: str
    cards: list[str]
    member_ids: list[str]


def build_seminar_group_lookup_time(*, day: str, time_text: str | None) -> str | None:
    day_text = str(day or "").strip()
    if not day_text:
        return None

    normalized_time = _normalize_time_text(time_text)
    if normalized_time:
        return f"{day_text} {normalized_time}"
    return day_text


def normalize_participant_cards(cards: list[Any] | None) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()
    for raw in cards or []:
        card = str(raw or "").strip()
        if not card or card in seen:
            continue
        seen.add(card)
        normalized.append(card)
    return normalized


def resolve_group_members(
    *,
    api: Any,
    participant_cards: list[str],
    organizer_card: str | None,
    lookup_room_id: Any | None = None,
    lookup_begin_time: str | None = None,
    lookup_end_time: str | None = None,
) -> dict[str, Any]:
    members: list[dict[str, Any]] = []
    seen_member_ids: set[str] = set()

    for card in normalize_participant_cards(participant_cards):
        if organizer_card and card == organizer_card:
            return {
                "ok": False,
                "reason": "self_in_participants",
                "detail": "Do not include the current account in --participant.",
                "card": card,
            }

        response = api.get_seminar_group(
            card=card,
            room_id=lookup_room_id,
            begin_time=lookup_begin_time,
            end_time=lookup_end_time,
        )
        if not is_success_response(response):
            return {
                "ok": False,
                "reason": "group_lookup_failed",
                "detail": response.get("msg", f"Failed to resolve participant: {card}"),
                "card": card,
                "response": response,
            }

        member = response.get("data")
        if not isinstance(member, dict) or member.get("id") is None:
            return {
                "ok": False,
                "reason": "group_lookup_invalid",
                "detail": f"Participant lookup returned incomplete data for {card}",
                "card": card,
                "response": response,
            }

        member_card = str(member.get("card") or member.get("username") or card).strip()
        if organizer_card and member_card == organizer_card:
            return {
                "ok": False,
                "reason": "self_in_participants",
                "detail": "Do not include the current account in --participant.",
                "card": card,
            }

        member_id = str(member["id"])
        if member_id in seen_member_ids:
            continue
        seen_member_ids.add(member_id)
        members.append(member)

    member_ids = [str(member["id"]) for member in members]
    return {
        "ok": True,
        "participants": SeminarResolvedParticipants(
            members=members,
            teamusers=",".join(member_ids),
            cards=[str(member.get("card") or member.get("username") or "").strip() for member in members],
            member_ids=member_ids,
        ),
    }


def _normalize_time_text(value: Any) -> str | None:
    text = str(value or "").strip()
    if not text:
        return None
    parts = text.split(":")
    if len(parts) < 2:
        return None
    return f"{int(parts[0]):02d}:{int(parts[1]):02d}"


def _time_to_minutes(value: str | None) -> int | None:
    if not value:
        return None
    hour, minute = (int(part) for part in value.split(":")[:2])
    return hour * 60 + minute


def _coerce_int(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return None


def _limit_to_minutes(value: Any) -> int | None:
    if value in (None, ""):
        return None
    if isinstance(value, str) and ":" in value:
        return _time_to_minutes(_normalize_time_text(value))

    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None

    if numeric <= 0:
        return None
    if numeric <= 24:
        return int(numeric * 60)
    return int(numeric)


def _parse_chinese_floor_number(text: str) -> int | None:
    value = text.strip()
    if not value:
        return None
    if value == "十":
        return 10
    if len(value) == 1:
        return _CHINESE_FLOOR_DIGITS.get(value)
    if value.startswith("十"):
        tail = _CHINESE_FLOOR_DIGITS.get(value[1:])
        return 10 + (tail or 0) if tail is not None else None
    if value.endswith("十"):
        head = _CHINESE_FLOOR_DIGITS.get(value[:-1])
        return head * 10 if head is not None else None
    if "十" in value:
        head_text, _, tail_text = value.partition("十")
        head = _CHINESE_FLOOR_DIGITS.get(head_text)
        tail = _CHINESE_FLOOR_DIGITS.get(tail_text)
        if head is None or tail is None:
            return None
        return head * 10 + tail
    return None


def _floor_sort_value(label: str) -> int | None:
    match = _FLOOR_DIGIT_RE.search(label)
    if match is not None:
        return int(match.group(1))

    for token in re.findall(r"[一二三四五六七八九十]+", label):
        parsed = _parse_chinese_floor_number(token)
        if parsed is not None:
            return parsed
    return None


def seminar_room_floor_label(room: dict[str, Any]) -> str:
    for key in ("floorName", "floor", "floorLabel"):
        text = str(room.get(key) or "").strip()
        if text:
            return text

    area_name = str(room.get("areaName") or "").strip()
    if area_name:
        return area_name
    return "未分层"


def sort_seminar_rooms(rooms: list[dict[str, Any]]) -> list[dict[str, Any]]:
    def _sort_key(room: dict[str, Any]) -> tuple[Any, ...]:
        area_name = str(room.get("areaName") or "").strip()
        floor_label = seminar_room_floor_label(room)
        floor_value = _floor_sort_value(floor_label)
        room_name = str(room.get("roomName") or room.get("label") or room.get("roomId") or "").strip()
        room_id = str(room.get("roomId") or "").strip()
        return (
            area_name,
            floor_value is None,
            floor_value if floor_value is not None else 999,
            floor_label,
            room_name,
            room_id,
        )

    return sorted(rooms, key=_sort_key)


def group_seminar_rooms_by_floor(rooms: list[dict[str, Any]]) -> list[tuple[str, list[dict[str, Any]]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    ordered_floors: list[str] = []
    for room in sort_seminar_rooms(rooms):
        floor_label = seminar_room_floor_label(room)
        if floor_label not in grouped:
            grouped[floor_label] = []
            ordered_floors.append(floor_label)
        grouped[floor_label].append(room)
    return [(floor_label, grouped[floor_label]) for floor_label in ordered_floors]


def _timestamp_to_hhmm(value: Any, time_zone: str) -> str | None:
    try:
        timestamp = int(str(value).strip())
    except (TypeError, ValueError):
        return None
    return datetime.fromtimestamp(timestamp, tz=resolve_time_zone(time_zone)).strftime("%H:%M")


def _normalize_blocked_range(item: Any, time_zone: str) -> dict[str, str] | None:
    if not isinstance(item, dict):
        return None

    start = _normalize_time_text(item.get("startTime")) or _timestamp_to_hhmm(item.get("beginTime"), time_zone)
    end = _normalize_time_text(item.get("endTime")) or _timestamp_to_hhmm(item.get("finishTime"), time_zone) or _timestamp_to_hhmm(item.get("endTime"), time_zone)
    if not start or not end:
        return None
    return {"startTime": start, "endTime": end}


def summarize_seminar_schedule(
    *,
    schedule_data: dict[str, Any] | None,
    detail_data: dict[str, Any] | None,
    time_zone: str,
) -> dict[str, Any]:
    payload = schedule_data if isinstance(schedule_data, dict) else {}
    detail = detail_data if isinstance(detail_data, dict) else {}
    blocked_ranges = [
        normalized
        for normalized in (_normalize_blocked_range(item, time_zone) for item in payload.get("list") or [])
        if normalized is not None
    ]
    return {
        "startTime": _normalize_time_text(payload.get("startTime")),
        "endTime": _normalize_time_text(payload.get("endTime")),
        "libraryCloseTime": LIBRARY_CLOSE_TIME,
        "minPerson": _coerce_int(payload.get("minPerson")),
        "maxPerson": _coerce_int(payload.get("maxPerson")),
        "minTime": payload.get("minTime"),
        "maxTime": payload.get("maxTime"),
        "minDurationMinutes": _limit_to_minutes(payload.get("minTime")),
        "maxDurationMinutes": _limit_to_minutes(payload.get("maxTime")),
        "blockedRanges": blocked_ranges,
        "uploadRequired": bool(int(str(detail.get("upload", 0) or 0))),
        "memberCount": _coerce_int(detail.get("membercount")),
    }


def validate_seminar_target(
    *,
    target: SeminarTarget,
    schedule_data: dict[str, Any] | None,
    detail_data: dict[str, Any] | None,
    participant_count: int,
    time_zone: str,
) -> dict[str, Any]:
    summary = summarize_seminar_schedule(schedule_data=schedule_data, detail_data=detail_data, time_zone=time_zone)
    target_start = _time_to_minutes(target.start_time)
    target_end = _time_to_minutes(target.end_time)
    if target_start is None or target_end is None or target_start >= target_end:
        return {
            "ok": False,
            "reason": "invalid_target_window",
            "detail": f"Invalid target window: {target.start_time}-{target.end_time}",
            "summary": summary,
        }

    if target_end > LIBRARY_CLOSE_MINUTES:
        return {
            "ok": False,
            "reason": "after_library_close",
            "detail": f"Target end time must be no later than {LIBRARY_CLOSE_TIME}.",
            "summary": summary,
        }

    schedule_start = _time_to_minutes(summary.get("startTime"))
    schedule_end = _time_to_minutes(summary.get("endTime"))
    if schedule_start is not None and target_start < schedule_start:
        return {
            "ok": False,
            "reason": "outside_open_window",
            "detail": "Target start time is earlier than the room opening window.",
            "summary": summary,
        }
    if schedule_end is not None and target_end > schedule_end:
        return {
            "ok": False,
            "reason": "outside_open_window",
            "detail": "Target end time is later than the room opening window.",
            "summary": summary,
        }

    duration_minutes = target_end - target_start
    min_duration = summary.get("minDurationMinutes")
    max_duration = summary.get("maxDurationMinutes")
    if min_duration is not None and duration_minutes < min_duration:
        return {
            "ok": False,
            "reason": "duration_too_short",
            "detail": f"Target duration is shorter than the room minimum ({min_duration} minutes).",
            "summary": summary,
        }
    if max_duration is not None and duration_minutes > max_duration:
        return {
            "ok": False,
            "reason": "duration_too_long",
            "detail": f"Target duration is longer than the room maximum ({max_duration} minutes).",
            "summary": summary,
        }

    for blocked in summary["blockedRanges"]:
        blocked_start = _time_to_minutes(blocked["startTime"])
        blocked_end = _time_to_minutes(blocked["endTime"])
        if blocked_start is None or blocked_end is None:
            continue
        if target_start < blocked_end and target_end > blocked_start:
            return {
                "ok": False,
                "reason": "blocked_range_conflict",
                "detail": f"Target window overlaps with a blocked range: {blocked['startTime']}-{blocked['endTime']}.",
                "summary": summary,
            }

    min_person = summary.get("minPerson")
    max_person = summary.get("maxPerson")
    min_extra = max(0, (min_person or 0) - 1)
    max_extra = None if max_person in (None, 0) else max(0, max_person - 1)
    if participant_count < min_extra:
        return {
            "ok": False,
            "reason": "insufficient_participants",
            "detail": f"At least {min_extra} additional participants are required for this room.",
            "summary": summary,
        }
    if max_extra is not None and participant_count > max_extra:
        return {
            "ok": False,
            "reason": "too_many_participants",
            "detail": f"At most {max_extra} additional participants are allowed for this room.",
            "summary": summary,
        }

    if summary["uploadRequired"]:
        return {
            "ok": False,
            "reason": "upload_required",
            "detail": "This seminar room requires material upload, which is not supported by the CLI yet.",
            "summary": summary,
        }

    return {"ok": True, "reason": None, "detail": None, "summary": summary}


def build_seminar_confirm_payload(
    *,
    target: SeminarTarget,
    defaults: SeminarDefaults,
    teamusers: str,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "day": target.day,
        "start_time": target.start_time,
        "end_time": target.end_time,
        "title": defaults.title,
        "content": defaults.content,
        "mobile": defaults.mobile,
        "room": target.room_id,
        "open": defaults.open,
        "file_name": "",
        "file_url": "",
        "id": 2,
    }
    if teamusers:
        payload["teamusers"] = teamusers
    return payload


def build_seminar_submit_payload(
    *,
    target: SeminarTarget,
    defaults: SeminarDefaults,
    teamusers: str,
) -> dict[str, Any]:
    return build_seminar_confirm_payload(target=target, defaults=defaults, teamusers=teamusers)

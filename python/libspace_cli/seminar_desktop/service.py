from __future__ import annotations

import json
import queue
import re
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Callable

from ..runtime_paths import ensure_runtime_dirs, resolve_named_runtime_paths
from ..seminar_service import LIBRARY_CLOSE_MINUTES, LIBRARY_CLOSE_TIME, group_seminar_rooms_by_floor, seminar_room_floor_label
from ..seminar_standalone import (
    SEMINAR_TOOL_CONFIG_NAME,
    _build_reservation_windows,
    _validate_trigger_time,
    discover_command,
    reserve_command,
)
from ..time_utils import get_zoned_day_string
from .models import ActionResult, DiscoverRoomCardData, DiscoverSnapshot, SeminarGuiFormData


DEFAULT_BASE_URL = "https://libspace.xauat.edu.cn"
DEFAULT_LANG = "zh"
DEFAULT_TRIGGER_TIME = "08:00:00"
DEFAULT_TIME_ZONE = "Asia/Shanghai"
VALUE_SPLIT_RE = re.compile(r"[\s,，、]+")


def _normalize_optional_text(value: Any) -> str:
    return str(value or "").strip()


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []

    output: list[str] = []
    for item in value:
        text = _normalize_optional_text(item)
        if text:
            output.append(text)
    return output


def _join_multiline(values: list[str]) -> str:
    return "\n".join(values)


def _split_text_values(text: str) -> list[str]:
    output: list[str] = []
    seen: set[str] = set()
    for raw in VALUE_SPLIT_RE.split(text.strip()):
        value = raw.strip()
        if not value or value in seen:
            continue
        seen.add(value)
        output.append(value)
    return output


def _coerce_room_id(token: str) -> Any:
    return int(token) if token.isdigit() else token


def _time_to_minutes(value: str) -> int:
    hour, minute = (int(part) for part in value.split(":")[:2])
    return hour * 60 + minute


def _coerce_duration_minutes(value: Any) -> int | None:
    text = _normalize_optional_text(value)
    if not text:
        return None
    if ":" in text:
        return _time_to_minutes(text)
    try:
        numeric = float(text)
    except ValueError:
        return None
    if numeric <= 0:
        return None
    if numeric <= 24:
        return int(numeric * 60)
    return int(numeric)


def resolve_discover_room_status(room: DiscoverRoomCardData, *, target_date: str) -> str:
    raw_room = room.raw_room if isinstance(room.raw_room, dict) else {}
    if room.upload_required:
        return "需上传材料"

    available_days = raw_room.get("availableDays")
    if isinstance(available_days, list) and available_days and target_date not in {str(item).strip() for item in available_days}:
        return "当天不可约"

    daily = raw_room.get("dailyAvailability") if isinstance(raw_room.get("dailyAvailability"), dict) else {}
    open_start = _coerce_duration_minutes(daily.get("startTime"))
    open_end = _coerce_duration_minutes(daily.get("endTime"))
    start_minutes = open_start if open_start is not None else 8 * 60
    end_minutes = open_end if open_end is not None else LIBRARY_CLOSE_MINUTES
    end_minutes = min(end_minutes, LIBRARY_CLOSE_MINUTES)
    if end_minutes <= start_minutes:
        return "无法预约"

    blocked_ranges = daily.get("blockedRanges") if isinstance(daily.get("blockedRanges"), list) else []
    normalized_ranges: list[tuple[int, int]] = []
    for blocked in blocked_ranges:
        if not isinstance(blocked, dict):
            continue
        start_text = _normalize_optional_text(blocked.get("startTime"))
        end_text = _normalize_optional_text(blocked.get("endTime"))
        if not start_text or not end_text:
            continue
        blocked_start = _time_to_minutes(start_text)
        blocked_end = _time_to_minutes(end_text)
        if blocked_end <= start_minutes or blocked_start >= end_minutes:
            continue
        normalized_ranges.append((max(start_minutes, blocked_start), min(end_minutes, blocked_end)))

    normalized_ranges.sort()
    merged_ranges: list[tuple[int, int]] = []
    for blocked_start, blocked_end in normalized_ranges:
        if not merged_ranges or blocked_start > merged_ranges[-1][1]:
            merged_ranges.append((blocked_start, blocked_end))
            continue
        last_start, last_end = merged_ranges[-1]
        merged_ranges[-1] = (last_start, max(last_end, blocked_end))

    minimum_gap = _coerce_duration_minutes(daily.get("minTime")) or 16
    cursor = start_minutes
    max_free_gap = 0
    for blocked_start, blocked_end in merged_ranges:
        max_free_gap = max(max_free_gap, blocked_start - cursor)
        cursor = max(cursor, blocked_end)
    max_free_gap = max(max_free_gap, end_minutes - cursor)

    if max_free_gap < minimum_gap:
        return "无法预约"
    return "可自动尝试"


def load_seminar_gui_form(config_path: Path) -> SeminarGuiFormData:
    if not config_path.exists():
        return SeminarGuiFormData()

    parsed = json.loads(config_path.read_text(encoding="utf-8"))
    if not isinstance(parsed, dict):
        raise ValueError("研讨室配置文件必须是 JSON 对象。")

    auth = parsed.get("auth") if isinstance(parsed.get("auth"), dict) else {}
    seminar = parsed.get("seminar") if isinstance(parsed.get("seminar"), dict) else {}
    defaults = seminar.get("defaults") if isinstance(seminar.get("defaults"), dict) else {}

    room_ids = [str(item) for item in seminar.get("priorityRoomIds", []) if str(item).strip()]
    participants = _string_list(seminar.get("participants"))

    return SeminarGuiFormData(
        username=_normalize_optional_text(auth.get("username")),
        password=_normalize_optional_text(auth.get("password")),
        trigger_time=_normalize_optional_text(seminar.get("triggerTime")) or DEFAULT_TRIGGER_TIME,
        start_time=_normalize_optional_text(seminar.get("startTime")),
        end_time=_normalize_optional_text(seminar.get("endTime")),
        participants_text=_join_multiline(participants),
        priority_room_ids_text=_join_multiline(room_ids),
        title=_normalize_optional_text(defaults.get("title")),
        content=_normalize_optional_text(defaults.get("content")),
        mobile=_normalize_optional_text(defaults.get("mobile")),
        open_value="0" if _normalize_optional_text(defaults.get("open")) == "0" else "1",
    )


def build_seminar_gui_config_payload(form: SeminarGuiFormData) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "baseUrl": DEFAULT_BASE_URL,
        "lang": DEFAULT_LANG,
        "seminar": {
            "triggerTime": _normalize_optional_text(form.trigger_time) or DEFAULT_TRIGGER_TIME,
            "startTime": _normalize_optional_text(form.start_time),
            "endTime": _normalize_optional_text(form.end_time),
            "participants": _split_text_values(form.participants_text),
            "defaults": {
                "title": _normalize_optional_text(form.title),
                "content": _normalize_optional_text(form.content),
                "mobile": _normalize_optional_text(form.mobile),
                "open": "0" if _normalize_optional_text(form.open_value) == "0" else "1",
            },
            "priorityRoomIds": [_coerce_room_id(item) for item in _split_text_values(form.priority_room_ids_text)],
        },
    }

    username = _normalize_optional_text(form.username)
    password = _normalize_optional_text(form.password)
    if username and password:
        payload["auth"] = {"username": username, "password": password}
    return payload


def save_seminar_gui_form(config_path: Path, form: SeminarGuiFormData) -> None:
    payload = build_seminar_gui_config_payload(form)
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def validate_seminar_gui_form(form: SeminarGuiFormData, *, action: str) -> list[str]:
    errors: list[str] = []
    username = _normalize_optional_text(form.username)
    password = _normalize_optional_text(form.password)

    if bool(username) != bool(password):
        errors.append("账号和密码必须同时填写，或者同时留空。")

    if action in {"discover", "reserve", "reserve_wait"} and not (username and password):
        errors.append("请填写统一身份认证账号和密码。")

    trigger_time = _normalize_optional_text(form.trigger_time) or DEFAULT_TRIGGER_TIME
    try:
        _validate_trigger_time(trigger_time)
    except ValueError as exc:
        errors.append(str(exc))

    if action in {"reserve", "reserve_wait"}:
        if not _normalize_optional_text(form.start_time):
            errors.append("请填写开始时间。")
        if not _normalize_optional_text(form.end_time):
            errors.append("请填写结束时间。")
        if not _normalize_optional_text(form.title):
            errors.append("请填写研讨主题。")
        if not _normalize_optional_text(form.content):
            errors.append("请填写研讨内容。")
        if not _normalize_optional_text(form.mobile):
            errors.append("请填写手机号。")
        if not _split_text_values(form.priority_room_ids_text):
            errors.append("请至少填写一个 roomId，并按优先顺序填写。")

        start_time = _normalize_optional_text(form.start_time)
        end_time = _normalize_optional_text(form.end_time)
        if start_time and end_time:
            try:
                _build_reservation_windows(start_time, end_time)
            except ValueError as exc:
                errors.append(str(exc))

    return errors


def build_discover_output_paths(runtime_dir: Path, target_date: str) -> tuple[Path, Path]:
    file_stem = f"seminar-tool-discover-{target_date.replace('-', '')}"
    return runtime_dir / f"{file_stem}.json", runtime_dir / f"{file_stem}.txt"


def _format_blocked_ranges(value: Any) -> str:
    if not isinstance(value, list) or not value:
        return "无"

    chunks: list[str] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        start_time = _normalize_optional_text(item.get("startTime"))
        end_time = _normalize_optional_text(item.get("endTime"))
        if start_time and end_time:
            chunks.append(f"{start_time}-{end_time}")
    return "、".join(chunks) if chunks else "无"


def load_discover_snapshot(runtime_dir: Path, target_date: str) -> DiscoverSnapshot | None:
    json_path, txt_path = build_discover_output_paths(runtime_dir, target_date)
    if not json_path.exists():
        return None

    payload = json.loads(json_path.read_text(encoding="utf-8"))
    rooms_payload = payload.get("rooms") if isinstance(payload.get("rooms"), list) else []
    rooms: list[DiscoverRoomCardData] = []
    for room in rooms_payload:
        if not isinstance(room, dict):
            continue
        daily = room.get("dailyAvailability") if isinstance(room.get("dailyAvailability"), dict) else {}
        start_time = _normalize_optional_text(daily.get("startTime")) or "--:--"
        end_time = _normalize_optional_text(daily.get("endTime")) or "--:--"
        min_person = _normalize_optional_text(daily.get("minPerson")) or "-"
        max_person = _normalize_optional_text(daily.get("maxPerson")) or "-"
        available_days = room.get("availableDays") if isinstance(room.get("availableDays"), list) else []
        available_text = "、".join(str(item) for item in available_days if str(item).strip()) or "-"

        rooms.append(
            DiscoverRoomCardData(
                room_id=str(room.get("roomId") or "-"),
                label=_normalize_optional_text(room.get("label")) or f"roomId {room.get('roomId')}",
                time_window=f"{start_time}-{end_time}  |  最晚不超过 {LIBRARY_CLOSE_TIME}",
                participant_range=f"{min_person}-{max_person} 人",
                blocked_ranges=_format_blocked_ranges(daily.get("blockedRanges")),
                available_days=available_text,
                upload_required=bool(room.get("uploadRequired")),
                member_count=_normalize_optional_text(room.get("memberCount")) or "-",
                raw_room=room,
            )
        )

    card_lookup = {room.room_id: room for room in rooms}
    ordered_rooms: list[DiscoverRoomCardData] = []
    normalized_rooms = [room for room in rooms_payload if isinstance(room, dict)]
    for _, floor_rooms in group_seminar_rooms_by_floor(normalized_rooms):
        for raw_room in floor_rooms:
            room_id = str(raw_room.get("roomId") or "-")
            card = card_lookup.get(room_id)
            if card is None:
                continue
            ordered_rooms.append(
                DiscoverRoomCardData(
                    room_id=card.room_id,
                    label=card.label,
                    time_window=card.time_window,
                    participant_range=card.participant_range,
                    blocked_ranges=card.blocked_ranges,
                    available_days=card.available_days,
                    upload_required=card.upload_required,
                    member_count=card.member_count,
                    floor_name=seminar_room_floor_label(raw_room),
                    raw_room=raw_room,
                )
            )
    rooms = ordered_rooms or rooms

    return DiscoverSnapshot(
        target_date=_normalize_optional_text(payload.get("targetDate")) or target_date,
        generated_at=_normalize_optional_text(payload.get("generatedAt")) or "",
        json_path=json_path,
        txt_path=txt_path if txt_path.exists() else None,
        rooms=rooms,
    )


def read_recent_log_lines(log_dir: Path, limit: int = 160) -> list[str]:
    files = sorted(log_dir.glob("*.jsonl"))
    if not files:
        return []

    formatted: list[str] = []
    for log_file in files:
        for raw_line in log_file.read_text(encoding="utf-8").splitlines():
            raw_line = raw_line.strip()
            if not raw_line:
                continue
            try:
                payload = json.loads(raw_line)
            except json.JSONDecodeError:
                formatted.append(raw_line)
                continue

            timestamp = _normalize_optional_text(payload.get("timestamp"))
            level = _normalize_optional_text(payload.get("level")).upper() or "INFO"
            message = _normalize_optional_text(payload.get("message")) or raw_line
            formatted.append(f"{timestamp} [{level}] {message}".strip())

    return formatted[-limit:]


class _StreamForwarder:
    def __init__(self, callback: Callable[[str], None] | None) -> None:
        self.callback = callback
        self.buffer = ""

    def write(self, text: str) -> int:
        if not text:
            return 0

        self.buffer += text
        while "\n" in self.buffer:
            line, self.buffer = self.buffer.split("\n", 1)
            if line.strip() and self.callback is not None:
                self.callback(line)
        return len(text)

    def flush(self) -> None:
        if self.buffer.strip() and self.callback is not None:
            self.callback(self.buffer)
        self.buffer = ""


class SeminarDesktopService:
    def __init__(self) -> None:
        self.paths = resolve_named_runtime_paths(config_name=SEMINAR_TOOL_CONFIG_NAME)
        ensure_runtime_dirs(self.paths)

    def load_form(self) -> SeminarGuiFormData:
        return load_seminar_gui_form(self.paths.config_path)

    def save_form(self, form: SeminarGuiFormData) -> None:
        save_seminar_gui_form(self.paths.config_path, form)

    def validate_form(self, form: SeminarGuiFormData, *, action: str) -> list[str]:
        return validate_seminar_gui_form(form, action=action)

    def load_latest_snapshot(self) -> DiscoverSnapshot | None:
        today = get_zoned_day_string(None, DEFAULT_TIME_ZONE)
        return load_discover_snapshot(self.paths.runtime_dir, today)

    def read_recent_logs(self, *, limit: int = 160) -> list[str]:
        return read_recent_log_lines(self.paths.log_dir, limit=limit)

    def room_doc_path(self) -> Path:
        return self.paths.root_dir.parent / "docs" / "seminar-room-id-table.md"

    def discover(self, *, log_callback: Callable[[str], None] | None = None) -> ActionResult:
        target_date = get_zoned_day_string(None, DEFAULT_TIME_ZONE)
        json_path, txt_path = build_discover_output_paths(self.paths.runtime_dir, target_date)
        writer = _StreamForwarder(log_callback)

        try:
            with redirect_stdout(writer), redirect_stderr(writer):
                exit_code = discover_command(SimpleNamespace(date=target_date))
        except Exception as exc:
            writer.write(f"{exc}\n")
            exit_code = 1
        writer.flush()

        snapshot = load_discover_snapshot(self.paths.runtime_dir, target_date)
        success = exit_code == 0 and snapshot is not None
        message = f"今日空闲研讨室已导出为 TXT：{txt_path}" if success else "获取今日空闲研讨室失败。"
        return ActionResult(
            success=success,
            exit_code=exit_code,
            message=message,
            json_path=json_path if json_path.exists() else None,
            txt_path=txt_path if txt_path.exists() else None,
            snapshot=snapshot,
        )

    def reserve(self, *, wait: bool, log_callback: Callable[[str], None] | None = None) -> ActionResult:
        writer = _StreamForwarder(log_callback)
        try:
            with redirect_stdout(writer), redirect_stderr(writer):
                exit_code = reserve_command(
                    SimpleNamespace(
                        date=None,
                        start=None,
                        end=None,
                        mobile=None,
                        participant=[],
                        room_id=None,
                        title=None,
                        content=None,
                        open=None,
                        trigger_time=None,
                        wait=wait,
                        force=not wait,
                    )
                )
        except Exception as exc:
            writer.write(f"{exc}\n")
            exit_code = 1
        writer.flush()

        message = "预约已提交。" if exit_code == 0 else "预约失败，请查看日志。"
        return ActionResult(success=exit_code == 0, exit_code=exit_code, message=message)

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class SeminarGuiFormData:
    username: str = ""
    password: str = ""
    trigger_time: str = "08:00:00"
    start_time: str = ""
    end_time: str = ""
    participants_text: str = ""
    priority_room_ids_text: str = ""
    title: str = ""
    content: str = ""
    mobile: str = ""
    open_value: str = "1"


@dataclass(frozen=True)
class DiscoverRoomCardData:
    room_id: str
    label: str
    time_window: str
    participant_range: str
    blocked_ranges: str
    available_days: str
    upload_required: bool
    member_count: str
    floor_name: str = ""
    raw_room: dict[str, Any] | None = None


@dataclass(frozen=True)
class DiscoverSnapshot:
    target_date: str
    generated_at: str
    json_path: Path | None
    txt_path: Path | None
    rooms: list[DiscoverRoomCardData]


@dataclass(frozen=True)
class ActionResult:
    success: bool
    exit_code: int
    message: str
    json_path: Path | None = None
    txt_path: Path | None = None
    snapshot: DiscoverSnapshot | None = None

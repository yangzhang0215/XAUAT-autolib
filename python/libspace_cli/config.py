from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any


DEFAULT_TIME_ZONE = "Asia/Shanghai"
TIME_RE = re.compile(r"^\d{2}:\d{2}:\d{2}$")
SELECTION_MODES = {"candidate_seats", "area_preferences"}
LOCAL_CONFIG_NAME = "config.local.json"


@dataclass(frozen=True)
class CandidateSeat:
    room_id: Any
    seat_ids: list[Any]


@dataclass(frozen=True)
class AuthConfig:
    username: str | None = None
    password: str | None = None


@dataclass(frozen=True)
class AreaMatch:
    area_name: str | None = None
    floor_name: str | None = None
    room_name: str | None = None

    def as_dict(self) -> dict[str, str]:
        output: dict[str, str] = {}
        if self.area_name is not None:
            output["areaName"] = self.area_name
        if self.floor_name is not None:
            output["floorName"] = self.floor_name
        if self.room_name is not None:
            output["roomName"] = self.room_name
        return output


@dataclass(frozen=True)
class AreaPreference:
    label: str
    room_id: Any | None
    match: AreaMatch | None
    seat_ids: list[Any]


@dataclass(frozen=True)
class Config:
    base_url: str
    trigger_time: str
    lang: str
    time_zone: str
    auth: AuthConfig
    selection_mode: str
    candidate_seats: list[CandidateSeat]
    area_preferences: list[AreaPreference]


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def _normalize_candidate(candidate: Any, index: int) -> CandidateSeat:
    _require(isinstance(candidate, dict), f"candidateSeats[{index}] must be an object")
    _require(candidate.get("roomId") is not None, f"candidateSeats[{index}].roomId is required")
    seat_ids = candidate.get("seatIds")
    _require(isinstance(seat_ids, list) and seat_ids, f"candidateSeats[{index}].seatIds must be a non-empty array")
    return CandidateSeat(room_id=candidate["roomId"], seat_ids=list(seat_ids))


def _normalize_area_match(match: Any, index: int) -> AreaMatch:
    _require(isinstance(match, dict), f"areaPreferences[{index}].match must be an object")
    area_name = match.get("areaName")
    floor_name = match.get("floorName")
    room_name = match.get("roomName")
    _require(
        any(isinstance(value, str) and value.strip() for value in (area_name, floor_name, room_name)),
        f"areaPreferences[{index}].match must include at least one of areaName/floorName/roomName",
    )
    return AreaMatch(
        area_name=area_name.strip() if isinstance(area_name, str) and area_name.strip() else None,
        floor_name=floor_name.strip() if isinstance(floor_name, str) and floor_name.strip() else None,
        room_name=room_name.strip() if isinstance(room_name, str) and room_name.strip() else None,
    )


def _normalize_area_preference(preference: Any, index: int) -> AreaPreference:
    _require(isinstance(preference, dict), f"areaPreferences[{index}] must be an object")
    label = preference.get("label")
    _require(isinstance(label, str) and label.strip(), f"areaPreferences[{index}].label is required")

    room_id = preference.get("roomId")
    raw_match = preference.get("match")
    _require(
        room_id is not None or raw_match is not None,
        f"areaPreferences[{index}] must provide roomId or match",
    )

    seat_ids = preference.get("seatIds", [])
    _require(isinstance(seat_ids, list), f"areaPreferences[{index}].seatIds must be an array")

    match = _normalize_area_match(raw_match, index) if room_id is None and raw_match is not None else None
    return AreaPreference(
        label=label.strip(),
        room_id=room_id,
        match=match,
        seat_ids=list(seat_ids),
    )


def _normalize_auth(auth: Any) -> AuthConfig:
    if auth is None:
        return AuthConfig()

    _require(isinstance(auth, dict), "config.auth must be an object")
    username = auth.get("username")
    password = auth.get("password")
    _require(isinstance(username, str) and username.strip(), "config.auth.username must be a non-empty string")
    _require(isinstance(password, str) and password.strip(), "config.auth.password must be a non-empty string")
    return AuthConfig(username=username.strip(), password=password.strip())


def resolve_config_path(config_path: Path) -> Path:
    local_override = config_path.with_name(LOCAL_CONFIG_NAME)
    return local_override if local_override.exists() else config_path


def load_config(config_path: Path) -> Config:
    source_path = resolve_config_path(config_path)
    if not source_path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")

    parsed = json.loads(source_path.read_text(encoding="utf-8"))
    _require(isinstance(parsed, dict), "Config must be a JSON object")
    _require(isinstance(parsed.get("baseUrl"), str) and parsed["baseUrl"], "config.baseUrl is required")
    _require(
        isinstance(parsed.get("triggerTime"), str) and TIME_RE.match(parsed["triggerTime"]) is not None,
        "config.triggerTime must be HH:MM:SS",
    )
    _require(isinstance(parsed.get("lang"), str) and parsed["lang"], "config.lang is required")
    if "auth" in parsed:
        _normalize_auth(parsed.get("auth"))
    _require(isinstance(parsed.get("candidateSeats", []), list), "config.candidateSeats must be an array")
    _require(isinstance(parsed.get("areaPreferences", []), list), "config.areaPreferences must be an array")

    selection_mode = str(parsed.get("selectionMode", "candidate_seats")).strip() or "candidate_seats"
    _require(selection_mode in SELECTION_MODES, f"config.selectionMode must be one of: {', '.join(sorted(SELECTION_MODES))}")

    return Config(
        base_url=parsed["baseUrl"].rstrip("/"),
        trigger_time=parsed["triggerTime"],
        lang=parsed["lang"],
        time_zone=DEFAULT_TIME_ZONE,
        auth=_normalize_auth(parsed.get("auth")),
        selection_mode=selection_mode,
        candidate_seats=[_normalize_candidate(item, index) for index, item in enumerate(parsed.get("candidateSeats", []))],
        area_preferences=[_normalize_area_preference(item, index) for index, item in enumerate(parsed.get("areaPreferences", []))],
    )

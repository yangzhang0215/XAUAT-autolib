from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .config import AuthConfig, DEFAULT_TIME_ZONE


TIME_RE = re.compile(r"^\d{2}:\d{2}:\d{2}$")
SHORT_TIME_RE = re.compile(r"^\d{2}:\d{2}$")


@dataclass(frozen=True)
class SeminarToolSettings:
    trigger_time: str | None
    start_time: str | None
    end_time: str | None
    participants: list[str]
    defaults: "SeminarToolDefaults"
    priority_room_ids: list[Any]


@dataclass(frozen=True)
class SeminarToolConfig:
    base_url: str
    lang: str
    time_zone: str
    auth: AuthConfig
    seminar: SeminarToolSettings


@dataclass(frozen=True)
class SeminarToolDefaults:
    title: str | None = None
    content: str | None = None
    mobile: str | None = None
    open: str | None = None


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def _normalize_optional_text(value: Any, field_name: str) -> str | None:
    if value is None:
        return None
    _require(isinstance(value, str), f"{field_name} must be a string")
    text = value.strip()
    return text or None


def _normalize_optional_short_time(value: Any, field_name: str) -> str | None:
    text = _normalize_optional_text(value, field_name)
    if text is None:
        return None
    _require(SHORT_TIME_RE.match(text) is not None, f"{field_name} must be HH:MM")
    hour, minute = (int(part) for part in text.split(":"))
    _require(0 <= hour <= 23 and 0 <= minute <= 59, f"{field_name} must be a valid 24-hour time")
    return text


def _normalize_auth(auth: Any) -> AuthConfig:
    if auth is None:
        return AuthConfig()

    _require(isinstance(auth, dict), "config.auth must be an object")
    username = auth.get("username")
    password = auth.get("password")
    _require(isinstance(username, str) and username.strip(), "config.auth.username must be a non-empty string")
    _require(isinstance(password, str) and password.strip(), "config.auth.password must be a non-empty string")
    return AuthConfig(username=username.strip(), password=password.strip())


def _normalize_open_value(value: Any, field_name: str) -> str:
    if isinstance(value, bool):
        return "1" if value else "0"
    if isinstance(value, int):
        if value in (0, 1):
            return str(value)
        raise ValueError(f"{field_name} must be 0/1 or true/false")

    text = str(value or "").strip().lower()
    if text in {"1", "true", "yes", "on"}:
        return "1"
    if text in {"0", "false", "no", "off"}:
        return "0"
    raise ValueError(f"{field_name} must be 0/1 or true/false")


def _normalize_optional_open_value(value: Any, field_name: str) -> str | None:
    if value is None:
        return None
    return _normalize_open_value(value, field_name)


def _normalize_defaults(raw_defaults: Any) -> SeminarToolDefaults:
    if raw_defaults is None:
        return SeminarToolDefaults()

    _require(isinstance(raw_defaults, dict), "config.seminar.defaults must be an object")
    return SeminarToolDefaults(
        title=_normalize_optional_text(raw_defaults.get("title"), "config.seminar.defaults.title"),
        content=_normalize_optional_text(raw_defaults.get("content"), "config.seminar.defaults.content"),
        mobile=_normalize_optional_text(raw_defaults.get("mobile"), "config.seminar.defaults.mobile"),
        open=_normalize_optional_open_value(raw_defaults.get("open"), "config.seminar.defaults.open"),
    )


def _normalize_priority_room_ids(raw_value: Any) -> list[Any]:
    if raw_value is None:
        return []
    _require(isinstance(raw_value, list), "config.seminar.priorityRoomIds must be an array")

    normalized: list[Any] = []
    for index, item in enumerate(raw_value):
        _require(item not in (None, ""), f"config.seminar.priorityRoomIds[{index}] must not be empty")
        normalized.append(item)
    return normalized


def _normalize_participants(raw_value: Any) -> list[str]:
    if raw_value is None:
        return []
    _require(isinstance(raw_value, list), "config.seminar.participants must be an array")

    normalized: list[str] = []
    seen: set[str] = set()
    for index, item in enumerate(raw_value):
        text = _normalize_optional_text(item, f"config.seminar.participants[{index}]")
        _require(text is not None, f"config.seminar.participants[{index}] must not be empty")
        if text in seen:
            continue
        seen.add(text)
        normalized.append(text)
    return normalized


def _normalize_seminar(raw_seminar: Any) -> SeminarToolSettings:
    if raw_seminar is None:
        return SeminarToolSettings(
            trigger_time=None,
            start_time=None,
            end_time=None,
            participants=[],
            defaults=SeminarToolDefaults(),
            priority_room_ids=[],
        )

    _require(isinstance(raw_seminar, dict), "config.seminar must be an object")
    trigger_time = raw_seminar.get("triggerTime")
    if trigger_time is not None:
        _require(
            isinstance(trigger_time, str) and TIME_RE.match(trigger_time.strip()) is not None,
            "config.seminar.triggerTime must be HH:MM:SS",
        )
    return SeminarToolSettings(
        trigger_time=trigger_time.strip() if isinstance(trigger_time, str) else None,
        start_time=_normalize_optional_short_time(raw_seminar.get("startTime"), "config.seminar.startTime"),
        end_time=_normalize_optional_short_time(raw_seminar.get("endTime"), "config.seminar.endTime"),
        participants=_normalize_participants(raw_seminar.get("participants")),
        defaults=_normalize_defaults(raw_seminar.get("defaults")),
        priority_room_ids=_normalize_priority_room_ids(raw_seminar.get("priorityRoomIds")),
    )


def load_seminar_tool_config(config_path: Path) -> SeminarToolConfig:
    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")

    parsed = json.loads(config_path.read_text(encoding="utf-8"))
    _require(isinstance(parsed, dict), "Config must be a JSON object")
    _require(isinstance(parsed.get("baseUrl"), str) and parsed["baseUrl"], "config.baseUrl is required")
    _require(isinstance(parsed.get("lang"), str) and parsed["lang"], "config.lang is required")

    return SeminarToolConfig(
        base_url=parsed["baseUrl"].rstrip("/"),
        lang=parsed["lang"],
        time_zone=DEFAULT_TIME_ZONE,
        auth=_normalize_auth(parsed.get("auth")),
        seminar=_normalize_seminar(parsed.get("seminar")),
    )

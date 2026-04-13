from __future__ import annotations

import json
from pathlib import Path
from typing import Any


DEFAULT_STATE: dict[str, Any] = {
    "token": None,
    "userInfo": None,
    "tokenSavedAt": None,
    "lastLogin": None,
    "lastReserve": None,
    "lastCancel": None,
    "lastSeminarReserve": None,
    "lastSeminarToolDiscover": None,
    "lastSeminarToolReserve": None,
}


def load_state(state_path: Path) -> dict[str, Any]:
    if not state_path.exists():
        return dict(DEFAULT_STATE)

    parsed = json.loads(state_path.read_text(encoding="utf-8"))
    state = dict(DEFAULT_STATE)
    state.update(parsed)
    return state


def save_state(state_path: Path, state: dict[str, Any]) -> None:
    state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")

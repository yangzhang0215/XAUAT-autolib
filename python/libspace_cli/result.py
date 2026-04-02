from __future__ import annotations

from typing import Any


def is_success_response(response: Any) -> bool:
    if not isinstance(response, dict):
        return False
    try:
        return int(response.get("code", 0)) == 1
    except (TypeError, ValueError):
        return False


def is_token_expired_response(response: Any) -> bool:
    if not isinstance(response, dict):
        return False
    return str(response.get("code")) == "10001"

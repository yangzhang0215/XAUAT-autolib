from __future__ import annotations

from typing import Any


ACTIVE_SEAT_BOOKING_STATUSES = {"1", "2", "9"}


def extract_member_seat_items(response: dict[str, Any]) -> list[dict[str, Any]]:
    data = response.get("data")
    if isinstance(data, list):
        return [item for item in data if isinstance(item, dict)]
    if isinstance(data, dict):
        for key in ("data", "list", "rows", "items"):
            items = data.get(key)
            if isinstance(items, list):
                return [item for item in items if isinstance(item, dict)]
    return []


def extract_active_seat_bookings(response: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        item
        for item in extract_member_seat_items(response)
        if str(item.get("status")) in ACTIVE_SEAT_BOOKING_STATUSES
    ]


def find_booking_by_id(response: dict[str, Any], booking_id: Any) -> dict[str, Any] | None:
    target = str(booking_id)
    for item in extract_member_seat_items(response):
        if str(item.get("id")) == target:
            return item
    return None

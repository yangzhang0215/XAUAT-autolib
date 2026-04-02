from __future__ import annotations

from typing import Any


def get_first_available_time_segment(day_row: dict[str, Any] | None) -> dict[str, Any] | None:
    for item in day_row.get("times", []) if day_row else []:
        if int(item.get("status", 0) or 0) == 1:
            return item
    return None


def get_first_available_seat(seat_ids: list[Any], seat_list: list[dict[str, Any]] | None) -> dict[str, Any] | None:
    available_seats = [
        seat
        for seat in (seat_list or [])
        if int(seat.get("status", 0) or 0) == 1
    ]
    if not seat_ids:
        return available_seats[0] if available_seats else None

    seat_map = {str(seat.get("id")): seat for seat in available_seats}
    for candidate_id in seat_ids:
        matched = seat_map.get(str(candidate_id))
        if matched:
            return matched
    return None

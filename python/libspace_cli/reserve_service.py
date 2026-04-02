from __future__ import annotations

from typing import Any

from .config import AreaPreference, CandidateSeat
from .seat_selection import get_first_available_seat, get_first_available_time_segment


def _normalize_text(value: Any) -> str:
    return str(value or "").strip()


def _room_matches_preference(room: dict[str, Any], preference: AreaPreference) -> bool:
    if preference.room_id is not None:
        return str(room.get("roomId")) == str(preference.room_id)

    if preference.match is None:
        return False

    if preference.match.area_name is not None and _normalize_text(room.get("areaName")) != preference.match.area_name:
        return False
    if preference.match.floor_name is not None and _normalize_text(room.get("floorName")) != preference.match.floor_name:
        return False
    if preference.match.room_name is not None and _normalize_text(room.get("roomName")) != preference.match.room_name:
        return False
    return True


def resolve_candidate_seats(
    *,
    selection_mode: str,
    candidate_seats: list[CandidateSeat],
    area_preferences: list[AreaPreference],
    valid_rooms: list[dict[str, Any]],
    logger: Any,
) -> list[CandidateSeat]:
    valid_room_ids = {str(room.get("roomId")) for room in valid_rooms}

    if selection_mode == "area_preferences":
        resolved: list[CandidateSeat] = []
        seen: set[tuple[str, tuple[str, ...]]] = set()

        for preference in area_preferences:
            matched_rooms = [room for room in valid_rooms if _room_matches_preference(room, preference)]
            if not matched_rooms:
                logger.warn("Area preference did not match any valid room", {"label": preference.label})
                continue

            for room in matched_rooms:
                candidate = CandidateSeat(room_id=room["roomId"], seat_ids=list(preference.seat_ids))
                key = (str(candidate.room_id), tuple(str(item) for item in candidate.seat_ids))
                if key in seen:
                    continue
                seen.add(key)
                resolved.append(candidate)

        return resolved

    resolved = []
    for candidate in candidate_seats:
        if str(candidate.room_id) in valid_room_ids:
            resolved.append(candidate)
        else:
            logger.warn("Configured room is not valid for target day and will be skipped", {"roomId": candidate.room_id})
    return resolved


def execute_reserve_once(
    *,
    api: Any,
    candidate_seats: list[CandidateSeat],
    target_day: str,
    logger: Any,
) -> dict[str, Any]:
    for candidate in candidate_seats:
        logger.info("Checking candidate room", {"roomId": candidate.room_id})

        room_date_response = api.get_seat_date({"build_id": candidate.room_id})
        if int(room_date_response.get("code", 0) or 0) != 1:
            return {
                "status": "api_error",
                "detail": f"Failed to get room date list for room {candidate.room_id}",
                "response": room_date_response,
            }

        day_row = next((item for item in room_date_response.get("data", []) if item.get("day") == target_day), None)
        if not day_row:
            logger.warn("Room is not bookable on target day", {"roomId": candidate.room_id, "targetDay": target_day})
            continue

        time_segment = get_first_available_time_segment(day_row)
        if not time_segment:
            logger.warn("Room has no active time segment", {"roomId": candidate.room_id, "targetDay": target_day})
            continue

        seat_list_response = api.get_seat_list(
            room_id=candidate.room_id,
            segment_id=time_segment.get("id"),
            day=day_row["day"],
            start_time=time_segment["start"],
            end_time=time_segment["end"],
        )
        if int(seat_list_response.get("code", 0) or 0) != 1:
            return {
                "status": "api_error",
                "detail": f"Failed to get seat list for room {candidate.room_id}",
                "response": seat_list_response,
            }

        seat = get_first_available_seat(candidate.seat_ids, seat_list_response.get("data"))
        if not seat:
            logger.warn("No configured seat is currently available in room", {"roomId": candidate.room_id})
            continue

        logger.info(
            "Submitting reservation request",
            {
                "roomId": candidate.room_id,
                "seatId": seat.get("id"),
                "seatName": seat.get("name"),
                "segmentId": time_segment.get("id"),
            },
        )
        confirm_response = api.confirm_seat(seat_id=seat.get("id"), segment_id=time_segment.get("id"))
        if int(confirm_response.get("code", 0) or 0) != 1:
            return {
                "status": "api_error",
                "detail": "Reservation confirmation failed",
                "response": confirm_response,
                "roomId": candidate.room_id,
                "seatId": seat.get("id"),
                "segmentId": time_segment.get("id"),
            }

        return {
            "status": "success",
            "response": confirm_response,
            "roomId": candidate.room_id,
            "seatId": seat.get("id"),
            "seatName": seat.get("name"),
            "segmentId": time_segment.get("id"),
            "day": day_row["day"],
        }

    return {
        "status": "no_available_seat",
        "detail": "No configured candidate seat is available",
    }

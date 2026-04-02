from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from libspace_cli.config import AreaMatch, AreaPreference, CandidateSeat
from libspace_cli.reserve_service import execute_reserve_once, resolve_candidate_seats


class _Logger:
    def info(self, message, context=None):
        return None

    def warn(self, message, context=None):
        return None

    def error(self, message, context=None):
        return None


class ReserveServiceTests(unittest.TestCase):
    def test_execute_reserve_once_falls_back_before_confirm(self) -> None:
        class Api:
            def __init__(self) -> None:
                self.confirm_calls = 0

            def get_seat_date(self, payload):
                if payload != {"build_id": 999}:
                    raise AssertionError(payload)
                return {
                    "code": 1,
                    "data": [
                        {
                            "day": "2026-04-01",
                            "times": [{"id": 77, "start": "07:00", "end": "22:30", "status": 1}],
                        }
                    ],
                }

            def get_seat_list(self, **payload):
                if payload["room_id"] != 999:
                    raise AssertionError(payload)
                return {
                    "code": 1,
                    "data": [
                        {"id": 2, "name": "B-02", "status": 1},
                        {"id": 3, "name": "B-03", "status": 1},
                    ],
                }

            def confirm_seat(self, *, seat_id, segment_id):
                self.confirm_calls += 1
                if {"seat_id": seat_id, "segment_id": segment_id} != {"seat_id": 2, "segment_id": 77}:
                    raise AssertionError((seat_id, segment_id))
                return {"code": 1, "msg": "ok"}

        api = Api()
        result = execute_reserve_once(
            api=api,
            candidate_seats=[CandidateSeat(room_id=999, seat_ids=[1, 2, 3])],
            target_day="2026-04-01",
            logger=_Logger(),
        )

        self.assertEqual(result["status"], "success")
        self.assertEqual(result["seatId"], 2)
        self.assertEqual(api.confirm_calls, 1)

    def test_execute_reserve_once_selects_first_available_seat_when_preference_is_empty(self) -> None:
        class Api:
            def get_seat_date(self, payload):
                return {
                    "code": 1,
                    "data": [
                        {
                            "day": "2026-04-01",
                            "times": [{"id": 77, "start": "07:00", "end": "22:30", "status": 1}],
                        }
                    ],
                }

            def get_seat_list(self, **payload):
                return {
                    "code": 1,
                    "data": [
                        {"id": 10, "name": "A-10", "status": 2},
                        {"id": 11, "name": "A-11", "status": 1},
                        {"id": 12, "name": "A-12", "status": 1},
                    ],
                }

            def confirm_seat(self, *, seat_id, segment_id):
                return {"code": 1, "msg": "ok", "seat_id": seat_id, "segment_id": segment_id}

        result = execute_reserve_once(
            api=Api(),
            candidate_seats=[CandidateSeat(room_id=999, seat_ids=[])],
            target_day="2026-04-01",
            logger=_Logger(),
        )

        self.assertEqual(result["status"], "success")
        self.assertEqual(result["seatId"], 11)

    def test_resolve_candidate_seats_filters_invalid_candidate_rooms(self) -> None:
        candidates = [
            CandidateSeat(room_id=101, seat_ids=[1, 2]),
            CandidateSeat(room_id=202, seat_ids=[3, 4]),
        ]
        valid_rooms = [{"roomId": 202}]

        result = resolve_candidate_seats(
            selection_mode="candidate_seats",
            candidate_seats=candidates,
            area_preferences=[],
            valid_rooms=valid_rooms,
            logger=_Logger(),
        )

        self.assertEqual([item.room_id for item in result], [202])

    def test_resolve_candidate_seats_supports_room_id_and_name_matching(self) -> None:
        valid_rooms = [
            {
                "roomId": 3,
                "areaName": "雁塔图书馆",
                "floorName": "二楼",
                "roomName": "南自修区",
            },
            {
                "roomId": 4,
                "areaName": "雁塔图书馆",
                "floorName": "二楼",
                "roomName": "北自修区",
            },
        ]
        preferences = [
            AreaPreference(label="exact-room", room_id=3, match=None, seat_ids=[3001, 3002]),
            AreaPreference(
                label="by-name",
                room_id=None,
                match=AreaMatch(area_name="雁塔图书馆", floor_name="二楼", room_name="北自修区"),
                seat_ids=[],
            ),
        ]

        result = resolve_candidate_seats(
            selection_mode="area_preferences",
            candidate_seats=[],
            area_preferences=preferences,
            valid_rooms=valid_rooms,
            logger=_Logger(),
        )

        self.assertEqual([(item.room_id, item.seat_ids) for item in result], [(3, [3001, 3002]), (4, [])])


if __name__ == "__main__":
    unittest.main()

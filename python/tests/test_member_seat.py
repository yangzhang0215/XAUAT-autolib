from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from libspace_cli.member_seat import extract_active_seat_bookings, extract_member_seat_items, find_booking_by_id


class MemberSeatTests(unittest.TestCase):
    def test_extract_member_seat_items_accepts_list_payload(self) -> None:
        response = {"code": 1, "data": [{"id": 1}, {"id": 2}]}
        self.assertEqual([item["id"] for item in extract_member_seat_items(response)], [1, 2])

    def test_extract_member_seat_items_accepts_nested_data_payload(self) -> None:
        response = {"code": 1, "data": {"data": [{"id": 3}, {"id": 4}]}}
        self.assertEqual([item["id"] for item in extract_member_seat_items(response)], [3, 4])

    def test_extract_active_bookings_filters_statuses(self) -> None:
        response = {
            "code": 1,
            "data": [
                {"id": 10, "status": 1},
                {"id": 20, "status": 2},
                {"id": 30, "status": 6},
                {"id": 40, "status": 9},
            ],
        }
        self.assertEqual([item["id"] for item in extract_active_seat_bookings(response)], [10, 20, 40])

    def test_find_booking_by_id_matches_stringified_ids(self) -> None:
        response = {"code": 1, "data": [{"id": 88, "status": 2}]}
        self.assertEqual(find_booking_by_id(response, "88"), {"id": 88, "status": 2})


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from libspace_cli.config import SeminarDefaults, SeminarTarget
from libspace_cli.seminar_service import (
    build_seminar_confirm_payload,
    build_seminar_group_lookup_time,
    group_seminar_rooms_by_floor,
    normalize_participant_cards,
    resolve_group_members,
    summarize_seminar_schedule,
    validate_seminar_target,
)


class _Api:
    def __init__(self, mapping):
        self.mapping = mapping
        self.group_calls = []

    def get_seminar_group(self, *, card, room_id=None, begin_time=None, end_time=None):
        self.group_calls.append(
            {
                "card": card,
                "room_id": room_id,
                "begin_time": begin_time,
                "end_time": end_time,
            }
        )
        return self.mapping[card]


class SeminarServiceTests(unittest.TestCase):
    def test_normalize_participant_cards_deduplicates_and_strips(self) -> None:
        self.assertEqual(
            normalize_participant_cards([" 2501 ", "", "2502", "2501", None]),
            ["2501", "2502"],
        )

    def test_resolve_group_members_rejects_self_card(self) -> None:
        result = resolve_group_members(
            api=_Api({}),
            participant_cards=["2504811004"],
            organizer_card="2504811004",
        )

        self.assertFalse(result["ok"])
        self.assertEqual(result["reason"], "self_in_participants")

    def test_resolve_group_members_deduplicates_same_member_id(self) -> None:
        api = _Api(
            {
                "2501": {"code": 1, "data": {"id": 7, "card": "2501", "name": "A"}},
                "2502": {"code": 1, "data": {"id": 7, "card": "2502", "name": "B"}},
                "2503": {"code": 1, "data": {"id": 8, "card": "2503", "name": "C"}},
            }
        )

        result = resolve_group_members(
            api=api,
            participant_cards=["2501", "2502", "2503"],
            organizer_card="9999",
            lookup_room_id=34,
            lookup_begin_time=build_seminar_group_lookup_time(day="2026-04-08", time_text="14:00"),
            lookup_end_time=build_seminar_group_lookup_time(day="2026-04-08", time_text="16:00"),
        )

        self.assertTrue(result["ok"])
        self.assertEqual(result["participants"].member_ids, ["7", "8"])
        self.assertEqual(result["participants"].teamusers, "7,8")
        self.assertEqual(
            api.group_calls[0],
            {
                "card": "2501",
                "room_id": 34,
                "begin_time": "2026-04-08 14:00",
                "end_time": "2026-04-08 16:00",
            },
        )

    def test_build_seminar_group_lookup_time_supports_day_only_and_time(self) -> None:
        self.assertEqual(
            build_seminar_group_lookup_time(day="2026-04-08", time_text="14:00"),
            "2026-04-08 14:00",
        )
        self.assertEqual(build_seminar_group_lookup_time(day="2026-04-08", time_text=None), "2026-04-08")

    def test_validate_seminar_target_checks_people_and_blocked_ranges(self) -> None:
        target = SeminarTarget(
            label="Wednesday PM",
            area_id=12,
            room_id=34,
            day="2026-04-08",
            start_time="14:00",
            end_time="16:00",
        )
        schedule_data = {
            "startTime": "08:00",
            "endTime": "22:00",
            "minPerson": 3,
            "maxPerson": 6,
            "list": [],
        }
        detail_data = {"upload": 0}

        not_enough_people = validate_seminar_target(
            target=target,
            schedule_data=schedule_data,
            detail_data=detail_data,
            participant_count=1,
            time_zone="Asia/Shanghai",
        )
        self.assertFalse(not_enough_people["ok"])
        self.assertEqual(not_enough_people["reason"], "insufficient_participants")

        blocked = validate_seminar_target(
            target=target,
            schedule_data={**schedule_data, "minPerson": 2, "list": [{"startTime": "15:00", "endTime": "15:30"}]},
            detail_data=detail_data,
            participant_count=2,
            time_zone="Asia/Shanghai",
        )
        self.assertFalse(blocked["ok"])
        self.assertEqual(blocked["reason"], "blocked_range_conflict")

    def test_validate_seminar_target_rejects_upload_required(self) -> None:
        target = SeminarTarget(
            label="Wednesday PM",
            area_id=12,
            room_id=34,
            day="2026-04-08",
            start_time="14:00",
            end_time="16:00",
        )

        result = validate_seminar_target(
            target=target,
            schedule_data={"startTime": "08:00", "endTime": "22:00", "minPerson": 1, "maxPerson": 0, "list": []},
            detail_data={"upload": 1},
            participant_count=0,
            time_zone="Asia/Shanghai",
        )

        self.assertFalse(result["ok"])
        self.assertEqual(result["reason"], "upload_required")

    def test_validate_seminar_target_rejects_after_library_close(self) -> None:
        target = SeminarTarget(
            label="Night session",
            area_id=12,
            room_id=34,
            day="2026-04-08",
            start_time="20:30",
            end_time="22:45",
        )

        result = validate_seminar_target(
            target=target,
            schedule_data={"startTime": "08:00", "endTime": "23:00", "minPerson": 1, "maxPerson": 0, "list": []},
            detail_data={"upload": 0},
            participant_count=0,
            time_zone="Asia/Shanghai",
        )

        self.assertFalse(result["ok"])
        self.assertEqual(result["reason"], "after_library_close")
        self.assertIn("22:30", result["detail"])

    def test_summarize_seminar_schedule_handles_timestamp_ranges_without_tzdata(self) -> None:
        summary = summarize_seminar_schedule(
            schedule_data={"list": [{"beginTime": 0, "finishTime": 1800}]},
            detail_data={"upload": 0},
            time_zone="Asia/Shanghai",
        )

        self.assertEqual(summary["blockedRanges"], [{"startTime": "08:00", "endTime": "08:30"}])

    def test_group_seminar_rooms_by_floor_sorts_floors(self) -> None:
        grouped = group_seminar_rooms_by_floor(
            [
                {"areaName": "图书馆", "floorName": "三楼", "roomName": "A301", "roomId": 71},
                {"areaName": "图书馆", "floorName": "二楼", "roomName": "A201", "roomId": 69},
                {"areaName": "图书馆", "floorName": "二楼", "roomName": "A202", "roomId": 70},
            ]
        )

        self.assertEqual([floor_name for floor_name, _ in grouped], ["二楼", "三楼"])
        self.assertEqual([room["roomId"] for room in grouped[0][1]], [69, 70])

    def test_build_seminar_confirm_payload_uses_expected_fields(self) -> None:
        payload = build_seminar_confirm_payload(
            target=SeminarTarget(
                label="Wednesday PM",
                area_id=12,
                room_id=34,
                day="2026-04-08",
                start_time="14:00",
                end_time="16:00",
            ),
            defaults=SeminarDefaults(title="Topic", content="Content", mobile="13800000000", open="1"),
            teamusers="7,8",
        )

        self.assertEqual(payload["day"], "2026-04-08")
        self.assertEqual(payload["room"], 34)
        self.assertEqual(payload["teamusers"], "7,8")
        self.assertEqual(payload["file_name"], "")
        self.assertEqual(payload["file_url"], "")
        self.assertEqual(payload["id"], 2)


if __name__ == "__main__":
    unittest.main()

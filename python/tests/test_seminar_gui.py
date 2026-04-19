from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from libspace_cli.seminar_desktop.models import DiscoverRoomCardData, SeminarGuiFormData
from libspace_cli.seminar_desktop.service import (
    build_discover_output_paths,
    build_seminar_gui_config_payload,
    load_discover_snapshot,
    load_seminar_gui_form,
    resolve_discover_room_status,
    validate_seminar_gui_form,
)


class SeminarGuiTests(unittest.TestCase):
    def _build_room(self, *, raw_room: dict) -> DiscoverRoomCardData:
        daily = raw_room.get("dailyAvailability", {})
        return DiscoverRoomCardData(
            room_id=str(raw_room.get("roomId", "58")),
            label=str(raw_room.get("label", "测试研讨室")),
            time_window=f"{daily.get('startTime') or '08:00'}-{daily.get('endTime') or '22:30'}",
            participant_range="2-4 人",
            blocked_ranges="-",
            available_days="2026-04-12",
            upload_required=bool(raw_room.get("uploadRequired")),
            member_count="4",
            raw_room=raw_room,
        )

    def test_load_seminar_gui_form_returns_defaults_when_config_missing(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "seminar.config.local.json"
            form = load_seminar_gui_form(config_path)

        self.assertEqual(form.trigger_time, "08:00:00")
        self.assertEqual(form.username, "")
        self.assertEqual(form.priority_room_ids_text, "")
        self.assertEqual(form.participants_text, "")

    def test_load_seminar_gui_form_reads_existing_values(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "seminar.config.local.json"
            config_path.write_text(
                json.dumps(
                    {
                        "baseUrl": "https://libspace.xauat.edu.cn",
                        "lang": "zh",
                        "auth": {"username": "2504811004", "password": "secret"},
                        "seminar": {
                            "triggerTime": "08:00:00",
                            "startTime": "12:00",
                            "endTime": "14:00",
                            "participants": ["2501", "2502"],
                            "priorityRoomIds": [69, 70, 71],
                            "defaults": {
                                "title": "课程讨论",
                                "content": "结构设计研讨",
                                "mobile": "13800000000",
                                "open": "0",
                            },
                        },
                    }
                ),
                encoding="utf-8",
            )

            form = load_seminar_gui_form(config_path)

        self.assertEqual(form.username, "2504811004")
        self.assertEqual(form.password, "secret")
        self.assertEqual(form.start_time, "12:00")
        self.assertEqual(form.end_time, "14:00")
        self.assertEqual(form.participants_text, "2501\n2502")
        self.assertEqual(form.priority_room_ids_text, "69\n70\n71")
        self.assertEqual(form.open_value, "0")

    def test_build_seminar_gui_config_payload_parses_multiline_values(self) -> None:
        form = SeminarGuiFormData(
            username="2504811004",
            password="secret",
            trigger_time="08:00:00",
            start_time="08:00",
            end_time="16:15",
            participants_text="2501,2502\n2501",
            priority_room_ids_text="69\n70,71",
            title="课程讨论",
            content="结构设计研讨",
            mobile="13800000000",
            open_value="0",
        )

        payload = build_seminar_gui_config_payload(form)

        self.assertEqual(payload["auth"]["username"], "2504811004")
        self.assertEqual(payload["seminar"]["participants"], ["2501", "2502"])
        self.assertEqual(payload["seminar"]["priorityRoomIds"], [69, 70, 71])
        self.assertEqual(payload["seminar"]["defaults"]["open"], "0")

    def test_validate_seminar_gui_form_requires_auth_for_reserve(self) -> None:
        errors = validate_seminar_gui_form(
            SeminarGuiFormData(
                start_time="12:00",
                end_time="14:00",
                priority_room_ids_text="69",
                title="课程讨论",
                content="结构设计研讨",
                mobile="13800000000",
            ),
            action="reserve",
        )

        self.assertTrue(any("账号和密码" in item for item in errors))

    def test_validate_seminar_gui_form_rejects_after_library_close(self) -> None:
        errors = validate_seminar_gui_form(
            SeminarGuiFormData(
                username="2504811004",
                password="secret",
                trigger_time="08:00:00",
                start_time="20:00",
                end_time="22:45",
                participants_text="2501\n2502",
                priority_room_ids_text="69\n70",
                title="课程讨论",
                content="结构设计研讨",
                mobile="13800000000",
                open_value="1",
            ),
            action="reserve_wait",
        )

        self.assertTrue(any("22:30" in item for item in errors))

    def test_validate_seminar_gui_form_accepts_long_multi_segment_span(self) -> None:
        errors = validate_seminar_gui_form(
            SeminarGuiFormData(
                username="2504811004",
                password="secret",
                trigger_time="08:00:00",
                start_time="08:00",
                end_time="20:00",
                participants_text="2501\n2502",
                priority_room_ids_text="69\n70",
                title="课程讨论",
                content="结构设计研讨",
                mobile="13800000000",
                open_value="1",
            ),
            action="reserve_wait",
        )

        self.assertEqual(errors, [])

    def test_load_discover_snapshot_reads_json_and_txt_paths(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime_dir = Path(temp_dir)
            json_path, txt_path = build_discover_output_paths(runtime_dir, "2026-04-12")
            json_path.write_text(
                json.dumps(
                    {
                        "generatedAt": "2026-04-12T08:00:00",
                        "targetDate": "2026-04-12",
                        "rooms": [
                            {
                                "roomId": 72,
                                "floorName": "三楼",
                                "label": "雁塔 / 三楼 / A-03",
                                "availableDays": ["2026-04-12"],
                                "uploadRequired": False,
                                "memberCount": 6,
                                "dailyAvailability": {
                                    "startTime": "09:00",
                                    "endTime": "21:00",
                                    "minPerson": 2,
                                    "maxPerson": 6,
                                    "blockedRanges": [],
                                },
                            },
                            {
                                "roomId": 69,
                                "floorName": "二楼",
                                "label": "雁塔 / 三层 / A-01",
                                "availableDays": ["2026-04-12"],
                                "uploadRequired": False,
                                "memberCount": 6,
                                "dailyAvailability": {
                                    "startTime": "08:00",
                                    "endTime": "22:00",
                                    "minPerson": 2,
                                    "maxPerson": 6,
                                    "blockedRanges": [{"startTime": "12:00", "endTime": "12:30"}],
                                },
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            txt_path.write_text("txt-summary", encoding="utf-8")

            snapshot = load_discover_snapshot(runtime_dir, "2026-04-12")

        self.assertIsNotNone(snapshot)
        assert snapshot is not None
        self.assertEqual(snapshot.rooms[0].room_id, "69")
        self.assertEqual(snapshot.rooms[0].floor_name, "二楼")
        self.assertEqual(snapshot.rooms[0].blocked_ranges, "12:00-12:30")
        self.assertIsInstance(snapshot.rooms[0].raw_room, dict)
        self.assertEqual(snapshot.txt_path, txt_path)

    def test_resolve_discover_room_status_marks_unavailable_when_only_15_minutes_left(self) -> None:
        room = self._build_room(
            raw_room={
                "roomId": 58,
                "label": "草堂图书馆 / 二楼 / 思（北）203",
                "availableDays": ["2026-04-12"],
                "uploadRequired": False,
                "dailyAvailability": {
                    "startTime": "08:00",
                    "endTime": "22:30",
                    "minTime": "60",
                    "blockedRanges": [
                        {"startTime": "08:00", "endTime": "14:30"},
                        {"startTime": "14:45", "endTime": "22:30"},
                    ],
                },
            }
        )

        status = resolve_discover_room_status(room, target_date="2026-04-12")

        self.assertEqual(status, "无法预约")

    def test_resolve_discover_room_status_marks_available_when_hour_window_exists(self) -> None:
        room = self._build_room(
            raw_room={
                "roomId": 40,
                "label": "草堂图书馆 / 三楼 / 学（南）302",
                "availableDays": ["2026-04-12"],
                "uploadRequired": False,
                "dailyAvailability": {
                    "startTime": "08:00",
                    "endTime": "22:30",
                    "minTime": "60",
                    "blockedRanges": [
                        {"startTime": "12:00", "endTime": "13:00"},
                        {"startTime": "18:30", "endTime": "22:30"},
                    ],
                },
            }
        )

        status = resolve_discover_room_status(room, target_date="2026-04-12")

        self.assertEqual(status, "可自动尝试")


if __name__ == "__main__":
    unittest.main()

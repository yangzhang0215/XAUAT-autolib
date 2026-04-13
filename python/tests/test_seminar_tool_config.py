from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from libspace_cli.seminar_tool_config import load_seminar_tool_config


class SeminarToolConfigTests(unittest.TestCase):
    def test_load_seminar_tool_config_parses_defaults_and_priority_rooms(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "seminar.config.local.json"
            config_path.write_text(
                json.dumps(
                    {
                        "baseUrl": "https://libspace.xauat.edu.cn",
                        "lang": "zh",
                        "auth": {"username": "2504811004", "password": "secret"},
                        "seminar": {
                            "triggerTime": "08:30:00",
                            "startTime": "08:00",
                            "endTime": "16:15",
                            "participants": ["2501", "2502", "2501"],
                            "defaults": {
                                "title": "Standalone topic",
                                "content": "Standalone content",
                                "mobile": "13800000000",
                                "open": True,
                            },
                            "priorityRoomIds": [34, 35, 36],
                        },
                    }
                ),
                encoding="utf-8",
            )

            config = load_seminar_tool_config(config_path)

        self.assertEqual(config.auth.username, "2504811004")
        self.assertEqual(config.seminar.trigger_time, "08:30:00")
        self.assertEqual(config.seminar.start_time, "08:00")
        self.assertEqual(config.seminar.end_time, "16:15")
        self.assertEqual(config.seminar.participants, ["2501", "2502"])
        self.assertEqual(config.seminar.defaults.title, "Standalone topic")
        self.assertEqual(config.seminar.defaults.content, "Standalone content")
        self.assertEqual(config.seminar.defaults.mobile, "13800000000")
        self.assertEqual(config.seminar.defaults.open, "1")
        self.assertEqual(config.seminar.priority_room_ids, [34, 35, 36])

    def test_load_seminar_tool_config_rejects_invalid_priority_room_ids(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "seminar.config.local.json"
            config_path.write_text(
                json.dumps(
                    {
                        "baseUrl": "https://libspace.xauat.edu.cn",
                        "lang": "zh",
                        "seminar": {
                            "triggerTime": "07:00:00",
                            "priorityRoomIds": [34, ""],
                        },
                    }
                ),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ValueError, "priorityRoomIds\\[1\\]"):
                load_seminar_tool_config(config_path)

    def test_load_seminar_tool_config_rejects_invalid_participants(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "seminar.config.local.json"
            config_path.write_text(
                json.dumps(
                    {
                        "baseUrl": "https://libspace.xauat.edu.cn",
                        "lang": "zh",
                        "seminar": {
                            "participants": ["2501", ""],
                        },
                    }
                ),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ValueError, "participants\\[1\\]"):
                load_seminar_tool_config(config_path)

    def test_load_seminar_tool_config_leaves_optional_values_empty_when_missing(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "seminar.config.local.json"
            config_path.write_text(
                json.dumps(
                    {
                        "baseUrl": "https://libspace.xauat.edu.cn",
                        "lang": "zh",
                        "seminar": {},
                    }
                ),
                encoding="utf-8",
            )

            config = load_seminar_tool_config(config_path)

        self.assertIsNone(config.seminar.trigger_time)
        self.assertIsNone(config.seminar.start_time)
        self.assertIsNone(config.seminar.end_time)
        self.assertEqual(config.seminar.participants, [])
        self.assertIsNone(config.seminar.defaults.title)
        self.assertIsNone(config.seminar.defaults.content)
        self.assertIsNone(config.seminar.defaults.mobile)
        self.assertIsNone(config.seminar.defaults.open)
        self.assertEqual(config.seminar.priority_room_ids, [])


if __name__ == "__main__":
    unittest.main()

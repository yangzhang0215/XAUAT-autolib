from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from libspace_cli.config import load_config, resolve_config_path


class ConfigTests(unittest.TestCase):
    def test_load_config_parses_auth_credentials(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "config.json"
            config_path.write_text(
                json.dumps(
                    {
                        "baseUrl": "https://libspace.xauat.edu.cn",
                        "triggerTime": "07:00:00",
                        "lang": "zh",
                        "auth": {"username": "2504811004", "password": "secret"},
                        "selectionMode": "candidate_seats",
                        "candidateSeats": [],
                        "areaPreferences": [],
                    }
                ),
                encoding="utf-8",
            )

            config = load_config(config_path)

        self.assertEqual(config.auth.username, "2504811004")
        self.assertEqual(config.auth.password, "secret")

    def test_load_config_rejects_empty_auth_credentials(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "config.json"
            config_path.write_text(
                json.dumps(
                    {
                        "baseUrl": "https://libspace.xauat.edu.cn",
                        "triggerTime": "07:00:00",
                        "lang": "zh",
                        "auth": {"username": "", "password": "secret"},
                        "selectionMode": "candidate_seats",
                        "candidateSeats": [],
                        "areaPreferences": [],
                    }
                ),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ValueError, "config.auth.username"):
                load_config(config_path)

    def test_load_config_prefers_config_local_override(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            config_path = temp_path / "config.json"
            config_local_path = temp_path / "config.local.json"
            config_path.write_text(
                json.dumps(
                    {
                        "baseUrl": "https://libspace.xauat.edu.cn",
                        "triggerTime": "07:00:00",
                        "lang": "zh",
                        "auth": {"username": "template-user", "password": "template-pass"},
                        "selectionMode": "candidate_seats",
                        "candidateSeats": [],
                        "areaPreferences": [],
                    }
                ),
                encoding="utf-8",
            )
            config_local_path.write_text(
                json.dumps(
                    {
                        "baseUrl": "https://libspace.xauat.edu.cn",
                        "triggerTime": "07:00:00",
                        "lang": "zh",
                        "auth": {"username": "local-user", "password": "local-pass"},
                        "selectionMode": "candidate_seats",
                        "candidateSeats": [],
                        "areaPreferences": [],
                    }
                ),
                encoding="utf-8",
            )

            self.assertEqual(resolve_config_path(config_path), config_local_path)
            config = load_config(config_path)

        self.assertEqual(config.auth.username, "local-user")
        self.assertEqual(config.auth.password, "local-pass")

    def test_load_config_parses_seminar_block(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "config.json"
            config_path.write_text(
                json.dumps(
                    {
                        "baseUrl": "https://libspace.xauat.edu.cn",
                        "triggerTime": "07:00:00",
                        "lang": "zh",
                        "auth": {"username": "2504811004", "password": "secret"},
                        "selectionMode": "candidate_seats",
                        "candidateSeats": [],
                        "areaPreferences": [],
                        "seminar": {
                            "triggerTime": "08:30:00",
                            "defaults": {
                                "title": "研讨主题",
                                "content": "研讨内容",
                                "mobile": "13800000000",
                                "open": True,
                            },
                            "targets": [
                                {
                                    "label": "周三下午",
                                    "areaId": 12,
                                    "roomId": 34,
                                    "day": "2026-04-08",
                                    "startTime": "14:00",
                                    "endTime": "16:00",
                                }
                            ],
                        },
                    }
                ),
                encoding="utf-8",
            )

            config = load_config(config_path)

        self.assertEqual(config.seminar.trigger_time, "08:30:00")
        self.assertEqual(config.seminar.defaults.open, "1")
        self.assertEqual(config.seminar.targets[0].room_id, 34)
        self.assertEqual(config.seminar.targets[0].start_time, "14:00")

    def test_load_config_rejects_incomplete_seminar_target(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "config.json"
            config_path.write_text(
                json.dumps(
                    {
                        "baseUrl": "https://libspace.xauat.edu.cn",
                        "triggerTime": "07:00:00",
                        "lang": "zh",
                        "selectionMode": "candidate_seats",
                        "candidateSeats": [],
                        "areaPreferences": [],
                        "seminar": {
                            "targets": [
                                {
                                    "label": "周三下午",
                                    "areaId": 12,
                                    "roomId": 34,
                                    "day": "2026-04-08",
                                    "startTime": "14:00",
                                }
                            ]
                        },
                    }
                ),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ValueError, "seminar.targets\\[0\\]\\.endTime"):
                load_config(config_path)


if __name__ == "__main__":
    unittest.main()

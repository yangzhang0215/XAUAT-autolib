from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from libspace_cli.commands import seminar_discover_command, seminar_reserve_command
from libspace_cli.config import AuthConfig, SeminarConfig, SeminarDefaults, SeminarTarget


class _Logger:
    def info(self, message, context=None):
        return None

    def warn(self, message, context=None):
        return None

    def error(self, message, context=None):
        return None


class _ReserveApi:
    def __init__(self) -> None:
        self.confirm_payloads = []
        self.group_calls = []

    def get_my_info(self):
        return {"code": 1, "data": {"card": "2504811004", "name": "tester"}}

    def get_seminar_detail(self, *, room_id):
        return {"code": 1, "data": {"upload": 0, "membercount": 6}}

    def get_seminar_schedule(self, *, room_id, area_id, day):
        return {
            "code": 1,
            "data": {
                "startTime": "08:00",
                "endTime": "22:00",
                "minPerson": 3,
                "maxPerson": 5,
                "list": [],
            },
        }

    def get_seminar_group(self, *, card, room_id=None, begin_time=None, end_time=None):
        self.group_calls.append(
            {
                "card": card,
                "room_id": room_id,
                "begin_time": begin_time,
                "end_time": end_time,
            }
        )
        member_id = {"2501": 11, "2502": 12}[card]
        return {"code": 1, "data": {"id": member_id, "card": card, "name": f"user-{card}"}}

    def confirm_seminar_reservation(self, payload):
        self.confirm_payloads.append(payload)
        return {"code": 1, "msg": "ok"}


class _DiscoverApi:
    def get_my_info(self):
        return {"code": 1, "data": {"card": "2504811004", "name": "tester"}}

    def get_seminar_tree(self, *, date):
        return {
            "code": 1,
            "data": [
                {
                    "id": 1,
                    "name": "雁塔图书馆",
                    "children": [
                        {
                            "id": 2,
                            "name": "二楼",
                            "children": [
                                {
                                    "id": 34,
                                    "name": "研讨室 A",
                                    "isValid": 1,
                                }
                            ],
                        }
                    ],
                }
            ],
        }

    def get_seminar_detail(self, *, room_id):
        return {"code": 1, "data": {"upload": 0, "membercount": 6}}

    def get_seminar_date(self, payload):
        return {"code": 1, "data": ["2026-04-08"]}

    def get_seminar_schedule(self, *, room_id, area_id, day):
        return {
            "code": 1,
            "data": {
                "startTime": "08:00",
                "endTime": "22:00",
                "minPerson": 3,
                "maxPerson": 6,
                "list": [],
            },
        }


class _Context:
    def __init__(self, api, runtime_dir: Path):
        self.api = api
        self.paths = SimpleNamespace(runtime_dir=runtime_dir)
        self.config = SimpleNamespace(
            auth=AuthConfig(username="config-user", password="config-pass"),
            base_url="https://libspace.xauat.edu.cn",
            time_zone="Asia/Shanghai",
            seminar=SeminarConfig(
                trigger_time="07:00:00",
                defaults=SeminarDefaults(
                    title="研讨主题",
                    content="研讨内容",
                    mobile="13800000000",
                    open="1",
                ),
                targets=[
                    SeminarTarget(
                        label="周三下午",
                        area_id=12,
                        room_id=34,
                        day="2026-04-08",
                        start_time="14:00",
                        end_time="16:00",
                    )
                ],
            ),
        )
        self.state = {
            "token": "cached-token",
            "userInfo": {"card": "2504811004"},
            "tokenSavedAt": None,
            "lastLogin": None,
            "lastReserve": None,
            "lastCancel": None,
            "lastSeminarReserve": None,
        }
        self.logger = _Logger()

    def persist_state(self):
        return None


class SeminarCommandTests(unittest.TestCase):
    def test_seminar_reserve_command_submits_once(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            ctx = _Context(_ReserveApi(), Path(temp_dir))
            args = SimpleNamespace(
                participant=["2501", "2502"],
                room_id="34",
                area_id="12",
                date="2026-04-08",
                start="14:00",
                end="16:00",
                title="主题",
                content="内容",
                mobile="13800000000",
                open="1",
                force=True,
            )

            with patch("libspace_cli.commands.create_command_context", return_value=ctx):
                code = seminar_reserve_command(args)

        self.assertEqual(code, 0)
        self.assertEqual(ctx.state["lastSeminarReserve"]["status"], "success")
        self.assertEqual(ctx.api.confirm_payloads[0]["teamusers"], "11,12")
        self.assertEqual(ctx.api.confirm_payloads[0]["id"], 2)
        self.assertEqual(
            ctx.api.group_calls[0],
            {
                "card": "2501",
                "room_id": "34",
                "begin_time": "2026-04-08 14:00",
                "end_time": "2026-04-08 16:00",
            },
        )

    def test_seminar_reserve_command_rejects_partial_explicit_target(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            ctx = _Context(_ReserveApi(), Path(temp_dir))
            args = SimpleNamespace(
                participant=["2501", "2502"],
                room_id="34",
                area_id=None,
                date="2026-04-08",
                start="14:00",
                end="16:00",
                title="主题",
                content="内容",
                mobile="13800000000",
                open="1",
                force=True,
            )

            with patch("libspace_cli.commands.create_command_context", return_value=ctx):
                code = seminar_reserve_command(args)

        self.assertEqual(code, 1)
        self.assertEqual(ctx.state["lastSeminarReserve"]["status"], "api_error")
        self.assertEqual(ctx.state["lastSeminarReserve"]["reason"], "invalid_arguments")

    def test_seminar_discover_command_writes_output(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            ctx = _Context(_DiscoverApi(), Path(temp_dir))
            args = SimpleNamespace(date="2026-04-08")

            with patch("libspace_cli.commands.create_command_context", return_value=ctx):
                code = seminar_discover_command(args)

            output_path = Path(temp_dir) / "seminar-discover-20260408.json"
            payload = json.loads(output_path.read_text(encoding="utf-8"))

        self.assertEqual(code, 0)
        self.assertEqual(len(payload["rooms"]), 1)
        self.assertEqual(payload["targetTemplate"][0]["roomId"], 34)
        self.assertEqual(payload["rooms"][0]["dailyAvailability"]["minPerson"], 3)


if __name__ == "__main__":
    unittest.main()

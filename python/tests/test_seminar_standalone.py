from __future__ import annotations

import json
import sys
import tempfile
import unittest
from datetime import date, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from libspace_cli.config import AuthConfig, SeminarDefaults
from libspace_cli.seminar_standalone import (
    _resolve_reserve_options,
    _resolve_schedule,
    discover_command,
    reserve_command,
)
from libspace_cli.time_utils import get_zoned_day_string

TEST_DAY = get_zoned_day_string(None, "Asia/Shanghai")
NEXT_DAY = (date.fromisoformat(TEST_DAY) + timedelta(days=1)).isoformat()


class _Logger:
    def info(self, message, context=None):
        return None

    def warn(self, message, context=None):
        return None

    def error(self, message, context=None):
        return None


class _Api:
    def __init__(
        self,
        *,
        upload_required_rooms: set[str] | None = None,
        unavailable_rooms: set[str] | None = None,
        group_fail_card: str | None = None,
        submit_fail_rooms: set[str] | None = None,
        submit_fail_windows: set[str] | None = None,
    ) -> None:
        self.upload_required_rooms = set(upload_required_rooms or set())
        self.unavailable_rooms = set(unavailable_rooms or set())
        self.group_fail_card = group_fail_card
        self.submit_fail_rooms = set(submit_fail_rooms or set())
        self.submit_fail_windows = set(submit_fail_windows or set())
        self.submit_payloads: list[dict[str, object]] = []

    def get_my_info(self):
        return {"code": 1, "data": {"card": "2504811004", "name": "tester"}}

    def get_seminar_tree(self, *, date):
        return {
            "code": 1,
            "data": [
                {
                    "id": 12,
                    "name": "Area",
                    "children": [
                        {
                            "id": 2,
                            "name": "Floor",
                            "children": [
                                {"id": 34, "name": "Seminar A", "isValid": 1},
                                {"id": 35, "name": "Seminar B", "isValid": 1},
                            ],
                        }
                    ],
                }
            ],
        }

    def get_seminar_date(self, payload):
        room_id = str(payload["build_id"])
        if room_id in self.unavailable_rooms:
            return {"code": 1, "data": [NEXT_DAY]}
        return {"code": 1, "data": [TEST_DAY]}

    def get_seminar_detail(self, *, room_id):
        upload = 1 if str(room_id) in self.upload_required_rooms else 0
        return {"code": 1, "data": {"upload": upload, "membercount": 6}}

    def get_seminar_schedule(self, *, room_id, area_id, day):
        return {
            "code": 1,
            "data": {
                "startTime": "08:00",
                "endTime": "22:00",
                "minPerson": 2,
                "maxPerson": 6,
                "list": [],
            },
        }

    def get_seminar_group(self, *, card):
        if card == self.group_fail_card:
            return {"code": 0, "msg": f"Failed to resolve participant: {card}"}
        mapping = {
            "2501": {"id": 11, "card": "2501", "name": "user-2501"},
            "2502": {"id": 12, "card": "2502", "name": "user-2502"},
        }
        return {"code": 1, "data": mapping[card]}

    def submit_seminar(self, payload):
        self.submit_payloads.append(payload)
        window_key = f"{payload['start_time']}-{payload['end_time']}"
        if str(payload["room"]) in self.submit_fail_rooms or window_key in self.submit_fail_windows:
            return {"code": 0, "msg": "submit failed"}
        return {"code": 1, "msg": "ok"}


class _Context:
    def __init__(
        self,
        api: _Api,
        root_dir: Path,
        priority_room_ids: list[int] | None = None,
        *,
        start_time: str | None = None,
        end_time: str | None = None,
        participants: list[str] | None = None,
    ):
        runtime_dir = root_dir / "runtime"
        runtime_dir.mkdir(parents=True, exist_ok=True)
        self.api = api
        self.paths = SimpleNamespace(
            root_dir=root_dir,
            runtime_dir=runtime_dir,
            state_path=runtime_dir / "state.json",
        )
        self.config = SimpleNamespace(
            auth=AuthConfig(username="config-user", password="config-pass"),
            base_url="https://libspace.xauat.edu.cn",
            lang="zh",
            time_zone="Asia/Shanghai",
            seminar=SimpleNamespace(
                trigger_time="07:00:00",
                start_time=start_time,
                end_time=end_time,
                participants=list(participants or []),
                defaults=SeminarDefaults(
                    title="Standalone topic",
                    content="Standalone content",
                    mobile="13800000000",
                    open="1",
                ),
                priority_room_ids=list([34, 35] if priority_room_ids is None else priority_room_ids),
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
            "lastSeminarToolDiscover": None,
            "lastSeminarToolReserve": None,
        }
        self.logger = _Logger()

    def persist_state(self):
        return None


class SeminarStandaloneTests(unittest.TestCase):
    def test_reserve_command_succeeds_with_explicit_room_id(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            ctx = _Context(_Api(), Path(temp_dir) / "python", priority_room_ids=[])
            args = SimpleNamespace(
                date=TEST_DAY,
                start="14:00",
                end="16:00",
                mobile="13800000000",
                participant=["2501"],
                room_id="35",
                title="Standalone topic",
                content="Standalone content",
                open="1",
                trigger_time=None,
                wait=False,
                force=True,
            )

            with patch("libspace_cli.seminar_standalone.create_seminar_tool_context", return_value=ctx), patch(
                "libspace_cli.seminar_standalone._can_prompt",
                return_value=False,
            ):
                code = reserve_command(args)

        self.assertEqual(code, 0)
        self.assertEqual(ctx.state["lastSeminarToolReserve"]["status"], "success")
        self.assertEqual(ctx.api.submit_payloads[0]["room"], 35)

    def test_reserve_command_falls_back_to_next_priority_room(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            ctx = _Context(_Api(upload_required_rooms={"34"}), Path(temp_dir) / "python", priority_room_ids=[34, 35])
            args = SimpleNamespace(
                date=TEST_DAY,
                start="14:00",
                end="16:00",
                mobile="13800000000",
                participant=["2501"],
                room_id=None,
                title="Standalone topic",
                content="Standalone content",
                open="1",
                trigger_time=None,
                wait=False,
                force=True,
            )

            with patch("libspace_cli.seminar_standalone.create_seminar_tool_context", return_value=ctx), patch(
                "libspace_cli.seminar_standalone._can_prompt",
                return_value=False,
            ):
                code = reserve_command(args)

        self.assertEqual(code, 0)
        self.assertEqual(ctx.api.submit_payloads[0]["room"], 35)

    def test_reserve_command_prefers_config_priority_room_over_cli_room_id(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            ctx = _Context(_Api(), Path(temp_dir) / "python", priority_room_ids=[34])
            args = SimpleNamespace(
                date=TEST_DAY,
                start="14:00",
                end="16:00",
                mobile="19999999999",
                participant=["2501"],
                room_id="35",
                title="CLI topic",
                content="CLI content",
                open="0",
                trigger_time="08:30:00",
                wait=False,
                force=True,
            )

            with patch("libspace_cli.seminar_standalone.create_seminar_tool_context", return_value=ctx), patch(
                "libspace_cli.seminar_standalone._can_prompt",
                return_value=False,
            ):
                code = reserve_command(args)

        self.assertEqual(code, 0)
        self.assertEqual(ctx.api.submit_payloads[0]["room"], 34)
        self.assertEqual(ctx.api.submit_payloads[0]["title"], "Standalone topic")
        self.assertEqual(ctx.api.submit_payloads[0]["content"], "Standalone content")
        self.assertEqual(ctx.api.submit_payloads[0]["mobile"], "13800000000")
        self.assertEqual(ctx.api.submit_payloads[0]["open"], "1")

    def test_reserve_command_uses_config_time_and_splits_into_two_submissions(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            ctx = _Context(
                _Api(),
                Path(temp_dir) / "python",
                priority_room_ids=[],
                start_time="08:00",
                end_time="16:15",
            )
            args = SimpleNamespace(
                date=TEST_DAY,
                start="10:00",
                end="12:00",
                mobile="13800000000",
                participant=["2501"],
                room_id="35",
                title="Standalone topic",
                content="Standalone content",
                open="1",
                trigger_time=None,
                wait=False,
                force=True,
            )

            with patch("libspace_cli.seminar_standalone.create_seminar_tool_context", return_value=ctx), patch(
                "libspace_cli.seminar_standalone._can_prompt",
                return_value=False,
            ):
                code = reserve_command(args)

        self.assertEqual(code, 0)
        self.assertEqual(len(ctx.api.submit_payloads), 2)
        self.assertEqual(ctx.api.submit_payloads[0]["start_time"], "08:00")
        self.assertEqual(ctx.api.submit_payloads[0]["end_time"], "12:00")
        self.assertEqual(ctx.api.submit_payloads[1]["start_time"], "12:15")
        self.assertEqual(ctx.api.submit_payloads[1]["end_time"], "16:15")

    def test_reserve_command_reports_participant_lookup_failure(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            ctx = _Context(_Api(group_fail_card="9999"), Path(temp_dir) / "python")
            args = SimpleNamespace(
                date=TEST_DAY,
                start="14:00",
                end="16:00",
                mobile="13800000000",
                participant=["9999"],
                room_id="35",
                title="Standalone topic",
                content="Standalone content",
                open="1",
                trigger_time=None,
                wait=False,
                force=True,
            )

            with patch("libspace_cli.seminar_standalone.create_seminar_tool_context", return_value=ctx), patch(
                "libspace_cli.seminar_standalone._can_prompt",
                return_value=False,
            ):
                code = reserve_command(args)

        self.assertEqual(code, 1)
        self.assertEqual(ctx.state["lastSeminarToolReserve"]["reason"], "group_lookup_failed")

    def test_reserve_command_rejects_self_in_participants(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            ctx = _Context(_Api(), Path(temp_dir) / "python")
            args = SimpleNamespace(
                date=TEST_DAY,
                start="14:00",
                end="16:00",
                mobile="13800000000",
                participant=["2504811004"],
                room_id="35",
                title="Standalone topic",
                content="Standalone content",
                open="1",
                trigger_time=None,
                wait=False,
                force=True,
            )

            with patch("libspace_cli.seminar_standalone.create_seminar_tool_context", return_value=ctx), patch(
                "libspace_cli.seminar_standalone._can_prompt",
                return_value=False,
            ):
                code = reserve_command(args)

        self.assertEqual(code, 1)
        self.assertEqual(ctx.state["lastSeminarToolReserve"]["reason"], "self_in_participants")

    def test_discover_command_writes_output(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            ctx = _Context(_Api(), Path(temp_dir) / "python")
            args = SimpleNamespace(date=TEST_DAY)

            with patch("libspace_cli.seminar_standalone.create_seminar_tool_context", return_value=ctx):
                code = discover_command(args)

            output_path = ctx.paths.runtime_dir / f"seminar-tool-discover-{TEST_DAY.replace('-', '')}.json"
            txt_output_path = ctx.paths.runtime_dir / f"seminar-tool-discover-{TEST_DAY.replace('-', '')}.txt"
            payload = json.loads(output_path.read_text(encoding="utf-8"))
            txt_payload = txt_output_path.read_text(encoding="utf-8")

        self.assertEqual(code, 0)
        self.assertEqual(payload["rooms"][0]["roomId"], 34)
        self.assertEqual(payload["targetTemplate"][0]["roomId"], 34)
        self.assertIn("独立研讨室今日空闲摘要", txt_payload)
        self.assertIn("roomId：34", txt_payload)

    def test_resolve_schedule_supports_long_wait_and_too_late(self) -> None:
        early = _resolve_schedule(
            trigger_time="07:00:00",
            time_zone="Asia/Shanghai",
            wait=True,
            now=datetime(2026, 4, 8, 6, 0, 0),
        )
        late = _resolve_schedule(
            trigger_time="07:00:00",
            time_zone="Asia/Shanghai",
            wait=True,
            now=datetime(2026, 4, 8, 7, 2, 0),
        )

        self.assertTrue(early.ok)
        self.assertEqual(early.delay_ms, 3600000)
        self.assertFalse(late.ok)
        self.assertEqual(late.reason, "too_late")

    def test_resolve_reserve_options_uses_cli_values_when_config_is_missing(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            ctx = _Context(_Api(), Path(temp_dir) / "python", priority_room_ids=[])
            ctx.config.seminar.trigger_time = None
            ctx.config.seminar.defaults = SimpleNamespace(
                title=None,
                content=None,
                mobile=None,
                open=None,
            )
            args = SimpleNamespace(
                date=TEST_DAY,
                start="14:00",
                end="16:00",
                mobile="19999999999",
                participant=["2501"],
                room_id="35",
                title="CLI topic",
                content="CLI content",
                open="0",
                trigger_time="08:30:00",
                wait=False,
                force=True,
            )

            request = _resolve_reserve_options(ctx, args, allow_prompt=False)

        self.assertEqual(request.room_id, "35")
        self.assertEqual(request.defaults.title, "CLI topic")
        self.assertEqual(request.defaults.content, "CLI content")
        self.assertEqual(request.defaults.mobile, "19999999999")
        self.assertEqual(request.defaults.open, "0")
        self.assertEqual(request.trigger_time, "08:30:00")
        self.assertEqual(len(request.windows), 1)
        self.assertEqual(request.windows[0].start_time, "14:00")
        self.assertEqual(request.windows[0].end_time, "16:00")

    def test_resolve_reserve_options_prefers_config_participants(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            ctx = _Context(
                _Api(),
                Path(temp_dir) / "python",
                priority_room_ids=[],
                participants=["2501", "2502"],
            )
            args = SimpleNamespace(
                date=TEST_DAY,
                start="14:00",
                end="16:00",
                mobile="19999999999",
                participant=["9999"],
                room_id="35",
                title="CLI topic",
                content="CLI content",
                open="0",
                trigger_time="08:30:00",
                wait=False,
                force=True,
            )

            request = _resolve_reserve_options(ctx, args, allow_prompt=False)

        self.assertEqual(request.participant_cards, ["2501", "2502"])

    def test_reserve_command_succeeds_with_config_participants_only(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            ctx = _Context(
                _Api(),
                Path(temp_dir) / "python",
                priority_room_ids=[],
                participants=["2501", "2502"],
            )
            args = SimpleNamespace(
                date=TEST_DAY,
                start="14:00",
                end="16:00",
                mobile="13800000000",
                participant=[],
                room_id="35",
                title="Standalone topic",
                content="Standalone content",
                open="1",
                trigger_time=None,
                wait=False,
                force=True,
            )

            with patch("libspace_cli.seminar_standalone.create_seminar_tool_context", return_value=ctx), patch(
                "libspace_cli.seminar_standalone._can_prompt",
                return_value=False,
            ):
                code = reserve_command(args)

        self.assertEqual(code, 0)
        self.assertEqual(ctx.state["lastSeminarToolReserve"]["status"], "success")
        self.assertEqual(ctx.state["lastSeminarToolReserve"]["participantCards"], ["2501", "2502"])

    def test_resolve_reserve_options_defaults_trigger_time_to_eight_am(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            ctx = _Context(_Api(), Path(temp_dir) / "python", priority_room_ids=[])
            ctx.config.seminar.trigger_time = None
            args = SimpleNamespace(
                date=TEST_DAY,
                start="14:00",
                end="16:00",
                mobile="19999999999",
                participant=["2501"],
                room_id="35",
                title="CLI topic",
                content="CLI content",
                open="0",
                trigger_time=None,
                wait=False,
                force=True,
            )

            request = _resolve_reserve_options(ctx, args, allow_prompt=False)

        self.assertEqual(request.trigger_time, "08:00:00")

    def test_resolve_reserve_options_rejects_non_current_day(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            ctx = _Context(_Api(), Path(temp_dir) / "python", priority_room_ids=[])
            args = SimpleNamespace(
                date=NEXT_DAY,
                start="14:00",
                end="16:00",
                mobile="19999999999",
                participant=["2501"],
                room_id="35",
                title="CLI topic",
                content="CLI content",
                open="0",
                trigger_time="08:30:00",
                wait=False,
                force=True,
            )

            with self.assertRaisesRegex(ValueError, "only support the current day"):
                _resolve_reserve_options(ctx, args, allow_prompt=False)

    def test_resolve_reserve_options_rejects_total_time_over_eight_hours(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            ctx = _Context(_Api(), Path(temp_dir) / "python", priority_room_ids=[])
            args = SimpleNamespace(
                date=TEST_DAY,
                start="08:00",
                end="16:30",
                mobile="19999999999",
                participant=["2501"],
                room_id="35",
                title="CLI topic",
                content="CLI content",
                open="0",
                trigger_time="08:30:00",
                wait=False,
                force=True,
            )

            with self.assertRaisesRegex(ValueError, "cannot exceed 8 hours"):
                _resolve_reserve_options(ctx, args, allow_prompt=False)

    def test_resolve_reserve_options_rejects_after_library_close(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            ctx = _Context(_Api(), Path(temp_dir) / "python", priority_room_ids=[])
            args = SimpleNamespace(
                date=TEST_DAY,
                start="20:00",
                end="22:45",
                mobile="19999999999",
                participant=["2501"],
                room_id="35",
                title="CLI topic",
                content="CLI content",
                open="0",
                trigger_time="08:30:00",
                wait=False,
                force=True,
            )

            with self.assertRaisesRegex(ValueError, "22:30"):
                _resolve_reserve_options(ctx, args, allow_prompt=False)


if __name__ == "__main__":
    unittest.main()

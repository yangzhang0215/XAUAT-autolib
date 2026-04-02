from __future__ import annotations

import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from libspace_cli.commands import cancel_seat_command


class _Logger:
    def info(self, message, context=None):
        return None

    def warn(self, message, context=None):
        return None

    def error(self, message, context=None):
        return None


class _Context:
    def __init__(self, api):
        self.api = api
        self.config = SimpleNamespace(time_zone="Asia/Shanghai")
        self.state = {"token": "cached-token"}
        self.logger = _Logger()
        self.persisted = False

    def persist_state(self):
        self.persisted = True


class _Api:
    def __init__(self, member_seat_responses):
        self.member_seat_responses = list(member_seat_responses)
        self.cancel_calls = []

    def get_my_info(self):
        return {"code": 1, "data": {"name": "tester"}}

    def get_member_seat(self, *, page=1, limit=100):
        if not self.member_seat_responses:
            raise AssertionError("Unexpected extra get_member_seat call")
        return self.member_seat_responses.pop(0)

    def cancel_space(self, *, reservation_id):
        self.cancel_calls.append(reservation_id)
        return {"code": 1, "msg": "ok"}


class CancelSeatCommandTests(unittest.TestCase):
    def test_cancel_seat_cancels_single_active_booking(self) -> None:
        api = _Api(
            [
                {"code": 1, "data": [{"id": 42, "status": 2, "statusName": "Reserved"}]},
                {"code": 1, "data": [{"id": 42, "status": 6, "statusName": "Cancelled"}]},
            ]
        )
        ctx = _Context(api)

        with patch("libspace_cli.commands.create_command_context", return_value=ctx), patch(
            "libspace_cli.commands.sleep_ms",
            return_value=None,
        ):
            code = cancel_seat_command(SimpleNamespace(id=None))

        self.assertEqual(code, 0)
        self.assertEqual(api.cancel_calls, [42])
        self.assertEqual(ctx.state["lastCancel"]["status"], "success")
        self.assertEqual(ctx.state["lastCancel"]["bookingStatusName"], "Cancelled")

    def test_cancel_seat_requires_id_when_multiple_active_bookings_exist(self) -> None:
        api = _Api(
            [
                {
                    "code": 1,
                    "data": [
                        {"id": 11, "status": 1, "statusName": "Booked"},
                        {"id": 22, "status": 2, "statusName": "Reserved"},
                    ],
                }
            ]
        )
        ctx = _Context(api)

        with patch("libspace_cli.commands.create_command_context", return_value=ctx):
            code = cancel_seat_command(SimpleNamespace(id=None))

        self.assertEqual(code, 1)
        self.assertEqual(api.cancel_calls, [])
        self.assertEqual(ctx.state["lastCancel"]["status"], "api_error")
        self.assertEqual(ctx.state["lastCancel"]["reason"], "multiple_active_bookings")

    def test_cancel_seat_marks_verification_pending_when_status_does_not_refresh(self) -> None:
        api = _Api(
            [
                {"code": 1, "data": [{"id": 99, "status": 2, "statusName": "Reserved"}]},
                {"code": 1, "data": [{"id": 99, "status": 2, "statusName": "Reserved"}]},
                {"code": 1, "data": [{"id": 99, "status": 2, "statusName": "Reserved"}]},
                {"code": 1, "data": [{"id": 99, "status": 2, "statusName": "Reserved"}]},
                {"code": 1, "data": [{"id": 99, "status": 2, "statusName": "Reserved"}]},
            ]
        )
        ctx = _Context(api)

        with patch("libspace_cli.commands.create_command_context", return_value=ctx), patch(
            "libspace_cli.commands.sleep_ms",
            return_value=None,
        ):
            code = cancel_seat_command(SimpleNamespace(id=None))

        self.assertEqual(code, 1)
        self.assertEqual(api.cancel_calls, [99])
        self.assertEqual(ctx.state["lastCancel"]["status"], "verification_pending")


if __name__ == "__main__":
    unittest.main()

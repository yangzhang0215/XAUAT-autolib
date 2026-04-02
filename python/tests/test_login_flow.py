from __future__ import annotations

import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from libspace_cli.authserver import DirectCasLoginResult
from libspace_cli.commands import _ensure_authenticated, login_command
from libspace_cli.config import AuthConfig


class _Logger:
    def info(self, message, context=None):
        return None

    def warn(self, message, context=None):
        return None

    def error(self, message, context=None):
        return None


class _Api:
    def __init__(self, *, my_info_responses=None):
        self.my_info_responses = list(my_info_responses or [])
        self.index_config_calls = 0
        self.exchange_calls: list[str] = []
        self.current_token = None

    def set_token(self, token):
        self.current_token = token

    def get_index_config(self):
        self.index_config_calls += 1
        return {
            "code": 1,
            "data_decrypted": {
                "config": {
                    "login": "4",
                    "cas_url": "/api/cas/cas",
                }
            },
        }

    def exchange_cas_ticket(self, cas):
        self.exchange_calls.append(cas)
        return {
            "code": 1,
            "member": {
                "token": "fresh-token",
                "card": "2504811004",
                "name": "tester",
            },
        }

    def get_my_info(self):
        if self.my_info_responses:
            return self.my_info_responses.pop(0)
        return {"code": 1, "data": {"name": "tester"}}


class _Context:
    def __init__(self, *, token=None, my_info_responses=None, auth=None):
        self.api = _Api(my_info_responses=my_info_responses)
        self.config = SimpleNamespace(
            auth=auth or AuthConfig(username="config-user", password="config-pass"),
            base_url="https://libspace.xauat.edu.cn",
            time_zone="Asia/Shanghai",
        )
        self.state = {
            "token": token,
            "userInfo": None,
            "tokenSavedAt": None,
            "lastLogin": None,
            "lastReserve": None,
            "lastCancel": None,
        }
        self.logger = _Logger()

    def persist_state(self):
        return None


class LoginFlowTests(unittest.TestCase):
    def test_login_command_uses_config_credentials_by_default(self) -> None:
        ctx = _Context()
        args = SimpleNamespace(username=None, password=None, url=None, cas=None)

        with patch("libspace_cli.commands.create_command_context", return_value=ctx), patch(
            "libspace_cli.commands.direct_cas_login",
            return_value=DirectCasLoginResult(status="success", message="ok", cas="ST-CONFIG-1"),
        ) as mocked_login:
            code = login_command(args)

        self.assertEqual(code, 0)
        self.assertEqual(ctx.state["token"], "fresh-token")
        self.assertEqual(ctx.state["lastLogin"]["status"], "success")
        self.assertEqual(ctx.state["lastLogin"]["credentialSource"], "config")
        mocked_login.assert_called_once()
        self.assertEqual(mocked_login.call_args.kwargs["username"], "config-user")
        self.assertEqual(mocked_login.call_args.kwargs["password"], "config-pass")

    def test_login_command_prefers_cli_credentials_over_config(self) -> None:
        ctx = _Context()
        args = SimpleNamespace(username="cli-user", password="cli-pass", url=None, cas=None)

        with patch("libspace_cli.commands.create_command_context", return_value=ctx), patch(
            "libspace_cli.commands.direct_cas_login",
            return_value=DirectCasLoginResult(status="success", message="ok", cas="ST-CLI-1"),
        ) as mocked_login:
            code = login_command(args)

        self.assertEqual(code, 0)
        self.assertEqual(ctx.state["lastLogin"]["credentialSource"], "cli")
        self.assertEqual(mocked_login.call_args.kwargs["username"], "cli-user")
        self.assertEqual(mocked_login.call_args.kwargs["password"], "cli-pass")

    def test_ensure_authenticated_logs_in_when_token_is_missing(self) -> None:
        ctx = _Context(token=None, my_info_responses=[{"code": 1, "data": {"name": "tester"}}])

        with patch(
            "libspace_cli.commands.direct_cas_login",
            return_value=DirectCasLoginResult(status="success", message="ok", cas="ST-AUTO-1"),
        ) as mocked_login:
            result = _ensure_authenticated(ctx)

        self.assertTrue(result["ok"])
        self.assertTrue(result["loginRefreshed"])
        self.assertEqual(ctx.state["token"], "fresh-token")
        mocked_login.assert_called_once()

    def test_ensure_authenticated_retries_when_token_is_expired(self) -> None:
        ctx = _Context(
            token="stale-token",
            my_info_responses=[
                {"code": 10001, "msg": "token expired"},
                {"code": 1, "data": {"name": "tester"}},
            ],
        )

        with patch(
            "libspace_cli.commands.direct_cas_login",
            return_value=DirectCasLoginResult(status="success", message="ok", cas="ST-RETRY-1"),
        ) as mocked_login:
            result = _ensure_authenticated(ctx)

        self.assertTrue(result["ok"])
        self.assertTrue(result["loginRefreshed"])
        self.assertEqual(ctx.state["token"], "fresh-token")
        mocked_login.assert_called_once()

    def test_ensure_authenticated_returns_auto_login_failure_for_captcha(self) -> None:
        ctx = _Context(token=None)

        with patch(
            "libspace_cli.commands.direct_cas_login",
            return_value=DirectCasLoginResult(
                status="captcha_required",
                message="captcha required",
                cas=None,
            ),
        ):
            result = _ensure_authenticated(ctx)

        self.assertFalse(result["ok"])
        self.assertEqual(result["reason"], "auto_login_failed")
        self.assertEqual(ctx.state["lastLogin"]["status"], "captcha_required")


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from libspace_cli.authserver import direct_cas_login, encrypt_authserver_password, extract_cas_value


class _Response:
    def __init__(self, *, url: str, text: str = "", json_data=None):
        self.url = url
        self.text = text
        self._json_data = json_data if json_data is not None else {}

    def json(self):
        return self._json_data


class _CaptchaRequiredSession:
    def __init__(self):
        self.post_called = False

    def get(self, url, **kwargs):
        if "checkNeedCaptcha.htl" in url:
            return _Response(url=url, json_data={"isNeed": True})
        return _Response(
            url="https://authserver.xauat.edu.cn/authserver/login?service=https%3A%2F%2Flibspace.xauat.edu.cn%2Fapi%2Fcas%2Fcas",
            text=(
                '<input type="hidden" name="execution" value="e1s1" />'
                '<input type="hidden" id="pwdEncryptSalt" value="2NrTGMaFPEsuzT7p" />'
                '<script>var contextPath = "/authserver";</script>'
            ),
        )

    def post(self, url, **kwargs):
        self.post_called = True
        raise AssertionError("POST should not be called when captcha is required")


class _AuthFailedSession:
    def get(self, url, **kwargs):
        if "checkNeedCaptcha.htl" in url:
            return _Response(url=url, json_data={"isNeed": False})
        return _Response(
            url="https://authserver.xauat.edu.cn/authserver/login?service=https%3A%2F%2Flibspace.xauat.edu.cn%2Fapi%2Fcas%2Fcas",
            text=(
                '<input type="hidden" name="execution" value="e1s1" />'
                '<input type="hidden" id="pwdEncryptSalt" value="2NrTGMaFPEsuzT7p" />'
                '<script>var contextPath = "/authserver";</script>'
            ),
        )

    def post(self, url, **kwargs):
        return _Response(
            url="https://authserver.xauat.edu.cn/authserver/login?service=https%3A%2F%2Flibspace.xauat.edu.cn%2Fapi%2Fcas%2Fcas",
            text='<div id="showErrorTip">用户名或密码错误</div>',
        )


class AuthserverTests(unittest.TestCase):
    def test_extract_cas_value_from_query_url(self) -> None:
        url = "https://libspace.xauat.edu.cn/h5/index.html?cas=ST-QUERY-001"
        self.assertEqual(extract_cas_value(url), "ST-QUERY-001")

    def test_extract_cas_value_from_hash_url(self) -> None:
        url = "https://libspace.xauat.edu.cn/h5/index.html#/cas/?cas=ST-HASH-002"
        self.assertEqual(extract_cas_value(url), "ST-HASH-002")

    def test_extract_cas_value_accepts_raw_value(self) -> None:
        self.assertEqual(extract_cas_value("ST-RAW-003"), "ST-RAW-003")

    def test_encrypt_authserver_password_is_stable_with_fixed_random_source(self) -> None:
        def fixed_random(length: int) -> str:
            return "A" * length

        encrypted = encrypt_authserver_password(
            "secret",
            "2NrTGMaFPEsuzT7p",
            random_provider=fixed_random,
        )
        self.assertEqual(
            encrypted,
            "ffL1tYT0/SWO6OncuT1+qxvSTqlrgE1cGjfttDCo2948u0hzZJDMvd8bt8AVRjcY0jnAZHfaRa1eoXt9i2Qv1nVvdLQWQn0ZplHjFCiKc14=",
        )

    def test_direct_cas_login_stops_when_captcha_is_required(self) -> None:
        session = _CaptchaRequiredSession()
        result = direct_cas_login(
            cas_entry_url="https://libspace.xauat.edu.cn/api/cas/cas",
            username="2504811004",
            password="secret",
            session=session,
        )
        self.assertEqual(result.status, "captcha_required")
        self.assertFalse(session.post_called)

    def test_direct_cas_login_returns_auth_failed_when_callback_is_missing(self) -> None:
        result = direct_cas_login(
            cas_entry_url="https://libspace.xauat.edu.cn/api/cas/cas",
            username="2504811004",
            password="secret",
            session=_AuthFailedSession(),
        )
        self.assertEqual(result.status, "auth_failed")
        self.assertIn("用户名或密码错误", result.message)


if __name__ == "__main__":
    unittest.main()

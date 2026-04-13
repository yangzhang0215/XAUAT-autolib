from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from libspace_cli.http import LibraryHttpClient


class _Response:
    def __init__(self) -> None:
        self.ok = True
        self.status_code = 200
        self.encoding = None
        self.content = (
            '{"code": 1, "msg": "浜屾ゼ", "nested": {"floorName": "浜屾ゼ"}}'.encode("utf-8")
        )

    def json(self):
        return {"code": 1, "msg": "浜屾ゼ", "nested": {"floorName": "浜屾ゼ"}}


class _Session:
    def __init__(self) -> None:
        self.response = _Response()

    def post(self, url, json, headers, timeout):
        return self.response


class HttpClientTests(unittest.TestCase):
    def test_post_forces_utf8_before_json_parsing(self) -> None:
        session = _Session()
        client = LibraryHttpClient(
            base_url="https://libspace.xauat.edu.cn",
            lang="zh",
            time_zone="Asia/Shanghai",
            session=session,
        )

        payload = client.post("/api/test", {})

        self.assertEqual(session.response.encoding, "utf-8")
        self.assertEqual(payload["msg"], "二楼")
        self.assertEqual(payload["nested"]["floorName"], "二楼")


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from libspace_cli.interfaces_catalog import build_interface_catalog, render_catalog_markdown


class InterfaceCatalogTests(unittest.TestCase):
    def test_catalog_has_expected_count_and_core_paths(self) -> None:
        records = build_interface_catalog()
        self.assertEqual(len(records), 124)

        endpoints = {(item["method"], item["path"]) for item in records}
        for expected in {
            ("POST", "/api/index/config"),
            ("GET", "/api/cas/cas"),
            ("POST", "/api/cas/user"),
            ("POST", "/api/Member/my"),
            ("POST", "/api/Seat/date"),
            ("POST", "/api/Seat/tree"),
            ("POST", "/api/Seat/seat"),
            ("POST", "/api/Seat/confirm"),
            ("POST", "/api/Seminar/date"),
            ("POST", "/api/Seminar/detail"),
            ("POST", "/api/Seminar/group"),
            ("POST", "/api/Seminar/seminar"),
            ("POST", "/api/Seminar/submit"),
            ("POST", "/api/Seminar/tree"),
            ("GET", "https://authserver.xauat.edu.cn/authserver/login"),
            ("POST", "https://authserver.xauat.edu.cn/authserver/login"),
            ("GET", "https://authserver.xauat.edu.cn/authserver/checkNeedCaptcha.htl"),
        }:
            self.assertIn(expected, endpoints)

    def test_markdown_render_includes_module_headers(self) -> None:
        rendered = render_catalog_markdown(build_interface_catalog())
        self.assertIn("## Login and index (20)", rendered)
        self.assertIn("## Seminar (13)", rendered)
        self.assertIn("## CAS authserver (3)", rendered)
        self.assertIn("| /api/Seat/confirm | POST |", rendered)
        self.assertIn("| /api/Seminar/submit | POST |", rendered)


if __name__ == "__main__":
    unittest.main()

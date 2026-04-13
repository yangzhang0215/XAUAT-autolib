from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from libspace_cli import runtime_paths


class RuntimePathsTests(unittest.TestCase):
    def test_resolve_data_path_uses_repo_root_in_source_mode(self) -> None:
        expected = runtime_paths.SOURCE_PYTHON_ROOT.parent / "docs" / "seminar-gui.md"
        self.assertEqual(runtime_paths.resolve_data_path("docs", "seminar-gui.md"), expected)

    def test_resolve_named_runtime_paths_uses_exe_directory_when_frozen(self) -> None:
        with (
            patch.object(runtime_paths.sys, "frozen", True, create=True),
            patch.object(runtime_paths.sys, "executable", r"C:\packed\xauat-seminar-gui.exe", create=True),
            patch.object(runtime_paths.sys, "_MEIPASS", r"C:\packed\bundle", create=True),
        ):
            resolved = runtime_paths.resolve_named_runtime_paths(config_name="seminar.config.local.json")

            self.assertEqual(resolved.root_dir, Path(r"C:\packed"))
            self.assertEqual(resolved.config_path, Path(r"C:\packed\seminar.config.local.json"))
            self.assertEqual(runtime_paths.resolve_data_path("assets", "xauat-emblem.ico"), Path(r"C:\packed\bundle\assets\xauat-emblem.ico"))


if __name__ == "__main__":
    unittest.main()

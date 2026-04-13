from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
from pathlib import Path


BOOTSTRAP_ENV = "SEMINAR_GUI_BOOTSTRAPPED"


def _has_gui_dependencies() -> bool:
    required = ("PySide6", "qfluentwidgets", "requests", "Crypto")
    return all(importlib.util.find_spec(name) is not None for name in required)


def _candidate_interpreters() -> list[Path]:
    project_root = Path(__file__).resolve().parents[1]
    candidates = [
        project_root / "python" / ".venv" / "Scripts" / "python.exe",
        project_root / ".venv" / "Scripts" / "python.exe",
    ]

    app_data = os.environ.get("APPDATA")
    if app_data:
        candidates.extend(sorted((Path(app_data) / "uv" / "python").glob("cpython-*/python.exe"), reverse=True))

    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        candidates.extend(sorted((Path(local_app_data) / "Programs" / "Python").glob("Python*/python.exe"), reverse=True))

    unique: list[Path] = []
    seen: set[str] = set()
    for candidate in candidates:
        try:
            resolved = candidate.resolve()
        except OSError:
            resolved = candidate
        key = str(resolved).lower()
        if key in seen or not resolved.exists():
            continue
        seen.add(key)
        unique.append(resolved)
    return unique


def _interpreter_supports_gui(interpreter: Path) -> bool:
    probe = (
        "import importlib.util as u, sys; "
        "required=('PySide6','qfluentwidgets','requests','Crypto'); "
        "sys.exit(0 if all(u.find_spec(name) for name in required) else 1)"
    )
    completed = subprocess.run([str(interpreter), "-c", probe], check=False)
    return completed.returncode == 0


def _relaunch_with_gui_interpreter() -> int | None:
    if os.environ.get(BOOTSTRAP_ENV) == "1":
        return None

    current = Path(sys.executable).resolve()
    for interpreter in _candidate_interpreters():
        if interpreter == current:
            continue
        if not _interpreter_supports_gui(interpreter):
            continue

        env = os.environ.copy()
        env[BOOTSTRAP_ENV] = "1"
        completed = subprocess.run([str(interpreter), str(Path(__file__).resolve()), *sys.argv[1:]], env=env, check=False)
        return completed.returncode

    return None


def main() -> int:
    if getattr(sys, "frozen", False):
        from libspace_cli.seminar_gui import main as gui_main

        return int(gui_main() or 0)

    if not _has_gui_dependencies():
        relaunched = _relaunch_with_gui_interpreter()
        if relaunched is not None:
            return relaunched

        print(
            "当前解释器未安装 PySide6 / qfluentwidgets，无法启动高级 GUI。\n"
            "建议先执行 `py -3 -m pip install -r python\\requirements.txt`，"
            "或者使用已安装这些依赖的 Python 解释器运行。",
            file=sys.stderr,
        )
        return 1

    from libspace_cli.seminar_gui import main as gui_main

    return int(gui_main() or 0)


if __name__ == "__main__":
    raise SystemExit(main())

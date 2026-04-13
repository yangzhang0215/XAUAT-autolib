from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

SOURCE_PYTHON_ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class RuntimePaths:
    root_dir: Path
    config_path: Path
    runtime_dir: Path
    log_dir: Path
    state_path: Path


def is_frozen_app() -> bool:
    return bool(getattr(sys, "frozen", False))


def resolve_bundle_root() -> Path:
    if is_frozen_app():
        bundle_root = getattr(sys, "_MEIPASS", None)
        if bundle_root:
            return Path(bundle_root)
        return Path(sys.executable).resolve().parent
    return SOURCE_PYTHON_ROOT


def resolve_data_root() -> Path:
    if is_frozen_app():
        return resolve_bundle_root()
    return SOURCE_PYTHON_ROOT.parent


def resolve_data_path(*parts: str) -> Path:
    return resolve_data_root().joinpath(*parts)


def resolve_app_root() -> Path:
    if is_frozen_app():
        return Path(sys.executable).resolve().parent
    return SOURCE_PYTHON_ROOT


def resolve_runtime_paths(root_dir: Path | None = None) -> RuntimePaths:
    return resolve_named_runtime_paths(root_dir=root_dir)


def resolve_named_runtime_paths(
    *,
    root_dir: Path | None = None,
    config_name: str = "config.local.json",
) -> RuntimePaths:
    root = Path(root_dir) if root_dir else resolve_app_root()
    runtime_dir = root / "runtime"
    log_dir = runtime_dir / "logs"
    return RuntimePaths(
        root_dir=root,
        config_path=root / config_name,
        runtime_dir=runtime_dir,
        log_dir=log_dir,
        state_path=runtime_dir / "state.json",
    )


def ensure_runtime_dirs(paths: RuntimePaths) -> None:
    paths.runtime_dir.mkdir(parents=True, exist_ok=True)
    paths.log_dir.mkdir(parents=True, exist_ok=True)

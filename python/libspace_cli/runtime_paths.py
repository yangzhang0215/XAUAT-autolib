from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class RuntimePaths:
    root_dir: Path
    config_path: Path
    runtime_dir: Path
    log_dir: Path
    state_path: Path


def resolve_runtime_paths(root_dir: Path | None = None) -> RuntimePaths:
    root = Path(root_dir) if root_dir else PROJECT_ROOT
    runtime_dir = root / "runtime"
    log_dir = runtime_dir / "logs"
    return RuntimePaths(
        root_dir=root,
        config_path=root / "config.local.json",
        runtime_dir=runtime_dir,
        log_dir=log_dir,
        state_path=runtime_dir / "state.json",
    )


def ensure_runtime_dirs(paths: RuntimePaths) -> None:
    paths.runtime_dir.mkdir(parents=True, exist_ok=True)
    paths.log_dir.mkdir(parents=True, exist_ok=True)

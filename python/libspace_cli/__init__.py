"""Python CLI for XAUAT libspace seat reservation."""

from __future__ import annotations

import sys
from pathlib import Path


def _ensure_site_packages_on_path() -> None:
    existing = {
        str(Path(entry).resolve())
        for entry in sys.path
        if entry and Path(entry).exists()
    }
    candidates: list[Path] = []

    for entry in sys.path:
        if not entry:
            continue
        path = Path(entry)
        if path.name.lower() != "lib":
            continue
        candidate = path / "site-packages"
        if candidate.exists():
            candidates.append(candidate)

    for candidate in candidates:
        resolved = str(candidate.resolve())
        if resolved not in existing:
            sys.path.append(resolved)
            existing.add(resolved)


_ensure_site_packages_on_path()


from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from .runtime_paths import RuntimePaths


class JsonLogger:
    def __init__(self, paths: RuntimePaths, command_name: str) -> None:
        self.paths = paths
        self.command_name = command_name

    def _append(self, level: str, message: str, context: dict[str, Any] | None = None) -> None:
        timestamp = datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
        entry = {
            "timestamp": timestamp,
            "command": self.command_name,
            "level": level,
            "message": message,
        }
        if context:
            entry.update(context)

        log_file = self.paths.log_dir / f"{timestamp[:10]}.jsonl"
        with log_file.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry, ensure_ascii=False) + "\n")

        line = f"{timestamp} [{level.upper()}] {message}"
        print(line)

    def info(self, message: str, context: dict[str, Any] | None = None) -> None:
        self._append("info", message, context)

    def warn(self, message: str, context: dict[str, Any] | None = None) -> None:
        self._append("warn", message, context)

    def error(self, message: str, context: dict[str, Any] | None = None) -> None:
        self._append("error", message, context)


def create_logger(paths: RuntimePaths, command_name: str) -> JsonLogger:
    return JsonLogger(paths, command_name)

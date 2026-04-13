from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from .runtime_paths import RuntimePaths
from .time_utils import resolve_time_zone


class JsonLogger:
    def __init__(self, paths: RuntimePaths, command_name: str, *, time_zone: str = "Asia/Shanghai") -> None:
        self.paths = paths
        self.command_name = command_name
        self.time_zone = time_zone

    def _append(self, level: str, message: str, context: dict[str, Any] | None = None) -> None:
        tz = resolve_time_zone(self.time_zone)
        timestamp = datetime.now(tz).replace(microsecond=0).isoformat()
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


def create_logger(paths: RuntimePaths, command_name: str, *, time_zone: str = "Asia/Shanghai") -> JsonLogger:
    return JsonLogger(paths, command_name, time_zone=time_zone)

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .api import LibraryApi
from .config import Config, load_config
from .logger import JsonLogger, create_logger
from .runtime_paths import RuntimePaths, ensure_runtime_dirs, resolve_runtime_paths
from .state import load_state, save_state


@dataclass
class CommandContext:
    paths: RuntimePaths
    config: Config
    state: dict[str, Any]
    logger: JsonLogger
    api: LibraryApi

    def persist_state(self) -> None:
        save_state(self.paths.state_path, self.state)


def create_command_context(command_name: str) -> CommandContext:
    paths = resolve_runtime_paths()
    ensure_runtime_dirs(paths)
    config = load_config(paths.config_path)
    state = load_state(paths.state_path)
    logger = create_logger(paths, command_name, time_zone=config.time_zone)
    api = LibraryApi(
        base_url=config.base_url,
        lang=config.lang,
        time_zone=config.time_zone,
        token=state.get("token"),
    )
    return CommandContext(paths=paths, config=config, state=state, logger=logger, api=api)

"""Hermes 运行环境检查."""

import os
import shutil
from dataclasses import dataclass
from pathlib import Path

from ai_war_game.domain.errors import HermesUnavailableError

ENV_BIN = "AI_WAR_GAME_HERMES_BIN"
ENV_MODEL = "AI_WAR_GAME_HERMES_MODEL"
ENV_CONFIG = "AI_WAR_GAME_HERMES_CONFIG"
DEFAULT_BIN = "hermes"


@dataclass(slots=True)
class HermesEnvironmentCheck:
    def check(self) -> None:
        reasons: list[str] = []

        bin_value = os.environ.get(ENV_BIN, DEFAULT_BIN)
        if _resolve_executable(bin_value) is None:
            reasons.append(f"未找到 hermes 可执行文件 (env {ENV_BIN}={bin_value})")

        model = os.environ.get(ENV_MODEL, "").strip()
        if not model:
            reasons.append(f"环境变量 {ENV_MODEL} 未设置")

        config_value = os.environ.get(ENV_CONFIG, "").strip()
        if not config_value:
            reasons.append(f"环境变量 {ENV_CONFIG} 未设置")
        else:
            config_path = Path(config_value)
            if not config_path.is_file():
                reasons.append(f"hermes config 文件不存在或不可读: {config_path}")

        if reasons:
            raise HermesUnavailableError("; ".join(reasons))


def _resolve_executable(value: str) -> Path | None:
    candidate = Path(value)
    if candidate.is_file() and os.access(candidate, os.X_OK):
        return candidate
    found = shutil.which(value)
    return Path(found) if found else None

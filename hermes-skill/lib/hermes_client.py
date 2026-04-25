"""hermes-skill/lib/hermes_client.py — Hermes environment check + subprocess LLM call."""

import json
import os
import shutil
import subprocess
from pathlib import Path

ENV_BIN = "AI_WAR_GAME_HERMES_BIN"
ENV_MODEL = "AI_WAR_GAME_HERMES_MODEL"
ENV_CONFIG = "AI_WAR_GAME_HERMES_CONFIG"
DEFAULT_BIN = "hermes"
HERMES_TIMEOUT = 120.0


class HermesUnavailableError(Exception):
    """Hermes 环境检查失败。"""


class ScenarioGenerationError(Exception):
    """Hermes 调用本身失败。"""


class ScenarioInvalidError(Exception):
    """Hermes 返回结构不符合最小要求。"""


def check_environment() -> None:
    """检查 Hermes CLI / model / config 是否可用。失败时抛 HermesUnavailableError。"""
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
            reasons.append(f"hermes config 文件不存在: {config_path}")

    if reasons:
        raise HermesUnavailableError("; ".join(reasons))


def call_hermes(prompt: str) -> str:
    """调用 Hermes CLI 发送 prompt, 返回原始 stdout。失败时抛 ScenarioGenerationError。"""
    check_environment()
    bin_path = os.environ.get(ENV_BIN, DEFAULT_BIN)
    model = os.environ.get(ENV_MODEL, "")
    config_path = os.environ.get(ENV_CONFIG, "")

    argv = [
        bin_path,
        "skill",
        "run",
        "scenario-generator",
        "--model",
        model,
        "--config",
        config_path,
    ]
    try:
        completed = subprocess.run(
            argv,
            input=prompt,
            capture_output=True,
            text=True,
            timeout=HERMES_TIMEOUT,
            check=False,
        )
    except FileNotFoundError as exc:
        raise ScenarioGenerationError(f"hermes 未找到: {exc}") from exc

    if completed.returncode != 0:
        raise ScenarioGenerationError(
            f"hermes 退出码 {completed.returncode}: {completed.stderr.strip() or '(无 stderr)'}"
        )
    return completed.stdout


def parse_json_response(raw: str) -> dict:
    """解析 LLM JSON 输出, 失败时抛 ScenarioInvalidError。"""
    try:
        return dict(json.loads(raw))
    except (json.JSONDecodeError, ValueError, TypeError) as exc:
        raise ScenarioInvalidError(f"hermes 输出不是合法 JSON: {exc}; raw={raw[:200]!r}") from exc


def _resolve_executable(value: str) -> Path | None:
    candidate = Path(value)
    if candidate.is_file() and os.access(candidate, os.X_OK):
        return candidate
    found = shutil.which(value)
    return Path(found) if found else None

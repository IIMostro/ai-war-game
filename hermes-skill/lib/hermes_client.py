"""hermes-skill/lib/hermes_client.py — Hermes environment check + LLM call."""

import json
import os
import shutil
from pathlib import Path

from llm_client import llm_chat

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
    """检查 LLM 环境。direct 模式下检查 API key; hermes 模式下检查 CLI / model / config。"""
    mode = os.environ.get("AI_WAR_GAME_LLM_MODE", "hermes").strip().lower()

    if mode == "direct":
        api_key = os.environ.get("AI_WAR_GAME_LLM_API_KEY") or os.environ.get("OPENAI_API_KEY", "")
        if not api_key:
            raise HermesUnavailableError(
                "direct 模式需要设置 AI_WAR_GAME_LLM_API_KEY 或 OPENAI_API_KEY"
            )
        return

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
    """调用 LLM 生成剧本。使用 llm_client (direct 或 hermes 模式)。"""
    system_prompt = "You are a game scenario generator. Output only valid JSON."
    return llm_chat(system_prompt=system_prompt, user_message=prompt)


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

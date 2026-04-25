"""llm.py — Unified LLM abstraction via litellm."""

from __future__ import annotations

import json
import os
from typing import Any

# Attempt to import litellm; provide a lightweight stub if unavailable
try:
    import litellm  # type: ignore
except Exception:  # pragma: no cover - fallback for test environments without litellm
    class _LitellmStub:
        def __init__(self):
            self.completion = None  # type: ignore

    litellm = _LitellmStub()

ENV_MODEL = "AI_WAR_GAME_LLM_MODEL"
ENV_API_KEY = "AI_WAR_GAME_LLM_API_KEY"
ENV_API_BASE = "AI_WAR_GAME_LLM_API_BASE"
DEFAULT_MODEL = "openai/gpt-4o-mini"
MAX_RETRIES = 3


class LLMError(Exception):
    """Base LLM error."""


class LLMConfigError(LLMError):
    """Missing or invalid configuration."""


class LLMResponseError(LLMError):
    """LLM returned invalid/unexpected response."""


def _resolve_model(model: str | None) -> str:
    return model or os.environ.get(ENV_MODEL) or DEFAULT_MODEL


def _resolve_api_key() -> str | None:
    return os.environ.get(ENV_API_KEY) or os.environ.get("OPENAI_API_KEY")


def llm_call(
    system_prompt: str,
    user_message: str,
    model: str | None = None,
    temperature: float = 0.7,
    max_tokens: int = 2048,
    **kwargs: Any,
) -> str:
    """Call LLM with system prompt + user message, return text response."""
    resolved_model = _resolve_model(model)
    api_key = _resolve_api_key()
    api_base = os.environ.get(ENV_API_BASE)

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_message},
    ]

    completion_kwargs: dict[str, Any] = {
        "model": resolved_model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    if api_key:
        completion_kwargs["api_key"] = api_key
    if api_base:
        completion_kwargs["api_base"] = api_base

    try:
        response = litellm.completion(**completion_kwargs)
        return str(response.choices[0].message.content or "")
    except Exception as e:
        raise LLMResponseError(f"LLM call failed: {e}") from e


def llm_call_json(
    system_prompt: str,
    user_message: str,
    json_schema_hint: str | None = None,
    **kwargs: Any,
) -> dict:
    """Call LLM and parse response as JSON. Retries up to MAX_RETRIES times on failure."""
    enhanced_prompt = system_prompt
    if json_schema_hint:
        enhanced_prompt += f"\n\nRespond with valid JSON following this schema:\n{json_schema_hint}"
    else:
        enhanced_prompt += "\n\nRespond with valid JSON only, no other text."

    last_error = None
    for attempt in range(MAX_RETRIES):
        try:
            raw = llm_call(system_prompt=enhanced_prompt, user_message=user_message, **kwargs)
            # Strip markdown code fences if present
            if "```json" in raw:
                raw = raw.split("```json")[1].split("```")[0].strip()
            elif "```" in raw:
                raw = raw.split("```")[1].split("```")[0].strip()
            result = json.loads(raw)
            if not isinstance(result, dict):
                raise json.JSONDecodeError("Response is not a JSON object", raw, 0)
            return result
        except (json.JSONDecodeError, LLMResponseError) as e:
            last_error = e
            continue

    raise LLMResponseError(
        f"Failed to get valid JSON after {MAX_RETRIES} attempts: {last_error}"
    )

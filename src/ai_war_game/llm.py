"""llm.py — Unified LLM abstraction via litellm + direct Ollama support."""

from __future__ import annotations

import json
import os
import urllib.request
from typing import Any

ENV_MODEL = "AI_WAR_GAME_LLM_MODEL"
ENV_API_KEY = "AI_WAR_GAME_LLM_API_KEY"
ENV_API_BASE = "AI_WAR_GAME_LLM_API_BASE"
DEFAULT_MODEL = "openai/gpt-4o-mini"
DEFAULT_OLLAMA_BASE = "http://127.0.0.1:11434"
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


def _is_ollama_model(model: str) -> bool:
    return model.startswith("ollama/") or model.startswith("ollama_chat/")


def _strip_provider(model: str) -> str:
    """Strip provider prefix (e.g. 'ollama/qwen:9b' → 'qwen:9b')."""
    for prefix in ("ollama/", "ollama_chat/", "openai/", "anthropic/"):
        if model.startswith(prefix):
            return model[len(prefix) :]
    return model


def _call_ollama(
    model_name: str,
    messages: list[dict],
    temperature: float,
    max_tokens: int,
    api_base: str,
) -> str:
    """Direct HTTP call to Ollama API (bypasses litellm compatibility issues)."""
    url = api_base.rstrip("/") + "/api/chat"
    payload = {
        "model": model_name,
        "messages": messages,
        "stream": False,
        "options": {
            "temperature": temperature,
            "num_predict": max_tokens,
        },
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=600) as resp:
            body = json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        raise LLMResponseError(f"Ollama call failed: {e}") from e

    content = body.get("message", {}).get("content", "") or ""
    # Strip deepseek  tags (reasoning output)
    if "<think>" in content:
        content = content.split("</think>")[-1].strip()
    return str(content)


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

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_message},
    ]

    if _is_ollama_model(resolved_model):
        api_base = os.environ.get(ENV_API_BASE) or DEFAULT_OLLAMA_BASE
        raw_model = _strip_provider(resolved_model)
        return _call_ollama(raw_model, messages, temperature, max_tokens, api_base)

    # For non-Ollama models, use litellm
    try:
        import litellm  # type: ignore
    except Exception as e:
        raise LLMConfigError(f"litellm not available for model {resolved_model}: {e}") from e

    completion_kwargs: dict[str, Any] = {
        "model": resolved_model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    api_key = _resolve_api_key()
    api_base = os.environ.get(ENV_API_BASE)
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
    for _attempt in range(MAX_RETRIES):
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

    raise LLMResponseError(f"Failed to get valid JSON after {MAX_RETRIES} attempts: {last_error}")

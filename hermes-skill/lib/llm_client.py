"""llm_client.py — Thin LLM abstraction: direct API or Hermes CLI."""

import json
import os
import subprocess
import urllib.error
import urllib.request


def llm_chat(*, system_prompt: str, user_message: str, model: str | None = None) -> str:
    """Chat with an LLM. Returns response text.

    Uses AI_WAR_GAME_LLM_MODE to decide: direct (HTTP API) or hermes (CLI subprocess).
    Falls back to direct if hermes mode fails with binary not found.
    """
    mode = os.environ.get("AI_WAR_GAME_LLM_MODE", "hermes").strip().lower()

    if mode == "direct":
        return _direct_chat(system_prompt, user_message, model)

    try:
        return _hermes_chat(system_prompt, user_message, model)
    except FileNotFoundError:
        return _direct_chat(system_prompt, user_message, model)


def _direct_chat(system_prompt: str, user_message: str, model: str | None = None) -> str:
    """Call LLM via OpenAI-compatible HTTP API."""
    api_base = (
        os.environ.get("AI_WAR_GAME_LLM_API_BASE")
        or os.environ.get("OPENAI_BASE_URL")
        or "https://api.openai.com/v1"
    ).rstrip("/")
    api_key = os.environ.get("AI_WAR_GAME_LLM_API_KEY") or os.environ.get("OPENAI_API_KEY", "")
    model_name = (
        model
        or os.environ.get("AI_WAR_GAME_LLM_MODEL")
        or os.environ.get("AI_WAR_GAME_HERMES_MODEL", "gpt-4o")
    )

    if not api_key:
        raise ValueError("LLM direct mode requires AI_WAR_GAME_LLM_API_KEY or OPENAI_API_KEY")

    data = json.dumps({
        "model": model_name,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
    }).encode()

    req = urllib.request.Request(
        f"{api_base}/chat/completions",
        data=data,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=180) as resp:
            result = json.loads(resp.read())
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        raise RuntimeError(f"LLM API error {e.code}: {body}") from e
    except urllib.error.URLError as e:
        raise RuntimeError(f"LLM API unreachable: {e.reason}") from e

    try:
        return result["choices"][0]["message"]["content"]
    except (KeyError, IndexError) as e:
        msg = f"Unexpected LLM response format: {json.dumps(result, indent=2)[:500]}"
        raise RuntimeError(msg) from e


def _hermes_chat(system_prompt: str, user_message: str, model: str | None = None) -> str:
    """Call LLM via Hermes CLI subprocess (hermes chat -q)."""
    bin_path = os.environ.get("AI_WAR_GAME_HERMES_BIN", "hermes")
    prompt = f"{system_prompt}\n\n{user_message}"

    result = subprocess.run(
        [bin_path, "chat", "-q", prompt],
        capture_output=True, text=True, timeout=180, check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(f"Hermes error: {result.stderr.strip()}")
    return result.stdout.strip()

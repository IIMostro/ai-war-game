# Hermes 移除实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use subagent-driven-development (recommended) or executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove all Hermes Agent dependencies, replace with litellm-based LLM abstraction and in-process general decision system, making the project self-contained.

**Architecture:** Hermes was used as (1) player entry point via SKILL.md, (2) LLM backend via hermes_client.py subprocess, (3) multi-agent runtime via `hermes -p <id> chat`. All three are replaced: (1) Python REPL CLI, (2) litellm SDK, (3) in-process LLM calls with general personality from SQLite.

**Tech Stack:** Python 3.12+, litellm, SQLite (stdlib)

---

### Task 1: Create `src/ai_war_game/llm.py` — LLM abstraction layer

**Files:**
- Create: `src/ai_war_game/llm.py`
- Test: `tests/unit/test_llm.py`

- [ ] **Step 1: Write `src/ai_war_game/llm.py`**

```python
"""llm.py — Unified LLM abstraction via litellm."""

from __future__ import annotations

import json
import os
from typing import Any

import litellm

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
```

- [ ] **Step 2: Write `tests/unit/test_llm.py`**

```python
"""tests/unit/test_llm.py"""

from __future__ import annotations

import json
from unittest.mock import patch

import pytest
from litellm import ModelResponse

from ai_war_game.llm import (
    LLMConfigError,
    LLMResponseError,
    llm_call,
    llm_call_json,
)


class MockChoice:
    def __init__(self, content: str):
        self.message = self
        self.content = content


class MockResponse:
    def __init__(self, content: str):
        self.choices = [MockChoice(content)]


def _mock_completion(content: str):
    def mock(*args, **kwargs):
        return MockResponse(content)
    return mock


class TestLlmCall:
    def test_returns_text_on_success(self):
        with patch("ai_war_game.llm.litellm.completion", _mock_completion("hello world")):
            result = llm_call("system", "user", model="test/model")
        assert result == "hello world"

    def test_raises_on_completion_error(self):
        with patch("ai_war_game.llm.litellm.completion", side_effect=Exception("API error")):
            with pytest.raises(LLMResponseError, match="API error"):
                llm_call("sys", "user", model="test/model")


class TestLlmCallJson:
    def test_parses_valid_json(self):
        with patch("ai_war_game.llm.litellm.completion", _mock_completion('{"key": "val"}')):
            result = llm_call_json("sys", "user", model="test/model")
        assert result == {"key": "val"}

    def test_strips_markdown_fences(self):
        with patch(
            "ai_war_game.llm.litellm.completion",
            _mock_completion('```json\n{"key": "val"}\n```'),
        ):
            result = llm_call_json("sys", "user", model="test/model")
        assert result == {"key": "val"}

    def test_retries_on_invalid_json(self):
        with patch(
            "ai_war_game.llm.litellm.completion",
            _mock_completion("not-json"),
        ):
            with pytest.raises(LLMResponseError):
                llm_call_json("sys", "user", model="test/model")

    def test_raises_on_json_array(self):
        with patch(
            "ai_war_game.llm.litellm.completion",
            _mock_completion("[1, 2, 3]"),
        ):
            with pytest.raises(LLMResponseError):
                llm_call_json("sys", "user", model="test/model")
```

- [ ] **Step 3: Run tests**

```bash
uv run pytest tests/unit/test_llm.py -v
```
Expected: 5 tests pass

- [ ] **Step 4: Commit**

```bash
git add src/ai_war_game/llm.py tests/unit/test_llm.py
git commit -m "feat: add LLM abstraction layer (litellm)"
```

---

### Task 2: Create package scaffolding + data models

**Files:**
- Create: `src/ai_war_game/__init__.py`
- Create: `src/ai_war_game/models.py`
- Modify: `main.py`

- [ ] **Step 1: Write `src/ai_war_game/__init__.py`**

```python
"""AI War Game — AI-driven sandbox warfare game."""
__version__ = "0.2.0"
```

- [ ] **Step 2: Write `src/ai_war_game/models.py`**

```python
"""models.py — Domain data classes."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class Faction:
    id: str
    name: str


@dataclass(frozen=True, slots=True)
class City:
    id: str
    name: str
    x: int
    y: int
    terrain: str
    owner_faction_id: str


@dataclass(slots=True)
class General:
    id: str
    name: str
    war: int
    cmd: int
    intel: int
    politics: int
    charm: int
    loyalty: int | None
    troops: int
    food: int
    position_city_id: str
    faction_id: str
    is_player: bool
    personality: dict[str, Any] = field(default_factory=dict)
```

- [ ] **Step 3: Update `main.py` to use new package entry**

```python
"""Entry point. Use `uv run python -m ai_war_game` or `ai-war-game` CLI."""
from ai_war_game.cli import run_cli

if __name__ == "__main__":
    raise SystemExit(run_cli())
```

- [ ] **Step 4: Add litellm dependency to `pyproject.toml`**

Edit `pyproject.toml`:

```toml
[project]
name = "ai-war-game"
version = "0.2.0"
description = "AI-driven sandbox warfare game"
requires-python = ">=3.12"
dependencies = ["litellm>=1.60.0"]
```

- [ ] **Step 5: Install litellm + verify import**

```bash
uv sync
uv run python -c "from ai_war_game import __version__; print(__version__)"
```
Expected: `0.2.0`

- [ ] **Step 6: Commit**

```bash
git add src/ai_war_game/__init__.py src/ai_war_game/models.py main.py pyproject.toml uv.lock
git commit -m "chore: set up package scaffolding with litellm dependency"
```

---

### Task 3: Migrate `db.py` to `src/ai_war_game/db.py`

**Files:**
- Create: `src/ai_war_game/db.py`
- Reference: `hermes-skill/scripts/db.py`

- [ ] **Step 1: Create `src/ai_war_game/db.py` — copy library functions, remove CLI main**

Key changes from `hermes-skill/scripts/db.py`:
- Remove `main()` function and all argparse CLI code
- Change `get_db_path()` signature — no longer needs `script_file` parameter, use `__file__` relative resolution
- Keep all exportable functions: `create_schema`, `insert_faction`, `insert_city`, `insert_general`, `upsert_state`, `get_state`, `get_general`, `get_events`, `log_event`, `read_graph`, `add_triple`, `get_graph_path`, `init_scenario_data`

```python
"""db.py — SQLite database layer for AI War Game."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path


def get_db_path(db_arg: str | None = None) -> str:
    if db_arg is not None:
        return db_arg
    # src/ai_war_game/db.py → project root → data/game.db
    return str(Path(__file__).resolve().parent.parent.parent / "data" / "game.db")


def get_graph_path(db_path: str) -> str:
    db = Path(db_path)
    return str(db.with_name("graph.json"))


def create_schema(conn: sqlite3.Connection) -> None:
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS factions (
            id TEXT PRIMARY KEY, name TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS cities (
            id TEXT PRIMARY KEY, name TEXT NOT NULL,
            x INTEGER NOT NULL CHECK(x >= 0 AND x <= 1000),
            y INTEGER NOT NULL CHECK(y >= 0 AND y <= 1000),
            terrain TEXT NOT NULL CHECK(terrain IN ('平原', '山地', '水域', '森林')),
            owner_faction_id TEXT REFERENCES factions(id)
        );
        CREATE TABLE IF NOT EXISTS generals (
            id TEXT PRIMARY KEY, name TEXT NOT NULL,
            war INTEGER NOT NULL CHECK(war >= 1 AND war <= 100),
            cmd INTEGER NOT NULL CHECK(cmd >= 1 AND cmd <= 100),
            intel INTEGER NOT NULL CHECK(intel >= 1 AND intel <= 100),
            politics INTEGER NOT NULL CHECK(politics >= 1 AND politics <= 100),
            charm INTEGER NOT NULL CHECK(charm >= 1 AND charm <= 100),
            loyalty INTEGER CHECK(loyalty IS NULL OR (loyalty >= 1 AND loyalty <= 100)),
            troops INTEGER NOT NULL CHECK(troops >= 100 AND troops <= 100000),
            food INTEGER NOT NULL CHECK(food >= 1 AND food <= 365),
            position_city_id TEXT NOT NULL REFERENCES cities(id),
            faction_id TEXT NOT NULL REFERENCES factions(id),
            is_player INTEGER NOT NULL DEFAULT 0,
            personality TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS game_state (
            key TEXT PRIMARY KEY, value TEXT NOT NULL, updated_day INTEGER NOT NULL
        );
        CREATE TABLE IF NOT EXISTS events_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            game_day INTEGER NOT NULL, seq INTEGER NOT NULL,
            event_type TEXT NOT NULL, actor_id TEXT, target_id TEXT,
            details_json TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS general_memories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            general_id TEXT NOT NULL REFERENCES generals(id),
            game_day INTEGER NOT NULL,
            event_type TEXT NOT NULL,
            summary TEXT NOT NULL,
            details_json TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        );
    """)
    conn.commit()


# ... insert all the same functions from hermes-skill/scripts/db.py,
# but without the CLI main() function
```

- [ ] **Step 2: Verify existing db tests still work**

```bash
uv run pytest tests/unit/hermes_skill/test_db.py -v
```
If `tests/unit/hermes_skill/test_db.py` imports from `hermes-skill/scripts/db.py`, update pyproject.toml pythonpath to include `src` instead first:

```bash
# Temporarily update test paths or skip· We'll handle test paths in Task 11
```

- [ ] **Step 3: Commit**

```bash
git add src/ai_war_game/db.py
git commit -m "feat: migrate db.py to src/ai_war_game/db.py"
```

---

### Task 4: Migrate `view.py` to `src/ai_war_game/view.py`

**Files:**
- Create: `src/ai_war_game/view.py`
- Reference: `hermes-skill/scripts/view.py`

- [ ] **Step 1: Create `src/ai_war_game/view.py`**

Same approach as db.py:
- Copy `format_show()`, `format_general()`, `format_map()`, `format_events()` from `hermes-skill/scripts/view.py`
- Update imports to `from ai_war_game.db import get_db_path, get_events, get_general`
- Remove `main()` and all argparse code

```python
"""view.py — Display formatting for AI War Game."""

from __future__ import annotations

import json
import sqlite3

from ai_war_game.db import get_db_path, get_events, get_general


def format_show(conn: sqlite3.Connection, faction_id: str, player_id: str, player_name: str) -> list[str]:
    # identical body to hermes-skill/scripts/view.py
    ...


def format_general(conn: sqlite3.Connection, general_id: str) -> list[str]:
    ...


def format_map(conn: sqlite3.Connection) -> list[str]:
    ...


def format_events(events: list[dict]) -> list[str]:
    ...
```

For the complete function bodies, copy verbatim from `hermes-skill/scripts/view.py`.

- [ ] **Step 2: Verify import works**

```bash
uv run python -c "from ai_war_game.view import format_show, format_general, format_map, format_events; print('OK')"
```
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add src/ai_war_game/view.py
git commit -m "feat: migrate view.py to src/ai_war_game/view.py"
```

---

### Task 5: Migrate `time_engine.py` → `src/ai_war_game/engine.py`

**Files:**
- Create: `src/ai_war_game/engine.py`
- Reference: `hermes-skill/scripts/time_engine.py`

- [ ] **Step 1: Create `src/ai_war_game/engine.py`**

Copy all functions from `hermes-skill/scripts/time_engine.py`, but:
- Change `from db import ...` → `from ai_war_game.db import ...`
- Update `get_db_path()` calls to use new signature
- Remove `main()` and argparse code

Kept functions:
- `get_event_queue_path()`, `load_event_queue()`, `save_event_queue()`
- `schedule_event()`, `calc_season()`, `generate_weather()`
- `march_days()`, `consume_food()`, `consume_all_food()`
- `run_daily_checks()`, `process_due_events()`, `advance_time()`

- [ ] **Step 2: Verify import**

```bash
uv run python -c "from ai_war_game.engine import advance_time, calc_season; print('OK')"
```
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add src/ai_war_game/engine.py
git commit -m "feat: migrate time_engine.py to src/ai_war_game/engine.py"
```

---

### Task 6: Add memory functions for general decision system

**Files:**
- Modify: `src/ai_war_game/db.py` (already has `general_memories` table in `create_schema`)

- [ ] **Step 1: Add memory CRUD functions to `db.py`**

Append these to `src/ai_war_game/db.py`:

```python
def add_memory(
    conn: sqlite3.Connection,
    general_id: str,
    game_day: int,
    event_type: str,
    summary: str,
    details: dict | None = None,
) -> None:
    conn.execute(
        "INSERT INTO general_memories (general_id, game_day, event_type, summary, details_json) "
        "VALUES (?, ?, ?, ?, ?)",
        (general_id, game_day, event_type, summary, json.dumps(details or {}, ensure_ascii=False)),
    )
    conn.commit()


def get_memories(conn: sqlite3.Connection, general_id: str, limit: int = 10) -> list[dict]:
    cursor = conn.execute(
        "SELECT game_day, event_type, summary, details_json, created_at "
        "FROM general_memories WHERE general_id=? ORDER BY id DESC LIMIT ?",
        (general_id, limit),
    )
    return [
        {
            "game_day": row[0],
            "event_type": row[1],
            "summary": row[2],
            "details": json.loads(row[3]) if row[3] else {},
            "created_at": row[4],
        }
        for row in cursor.fetchall()
    ]
```

- [ ] **Step 2: Commit**

```bash
git add src/ai_war_game/db.py
git commit -m "feat: add general_memories CRUD to db.py"
```

---

### Task 7: Create general decision system (replaces `agent_comm.py`)

**Files:**
- Create: `src/ai_war_game/autonomy.py`

- [ ] **Step 1: Write `src/ai_war_game/autonomy.py`**

```python
"""autonomy.py — General AI decision making (replaces agent_comm.py Hermes subprocess)."""

from __future__ import annotations

import json
import sqlite3

from ai_war_game.db import add_memory, get_general, get_memories
from ai_war_game.llm import llm_call_json


def _build_personality_prompt(general: dict, memory_summary: str) -> str:
    """Build system prompt from general's personality JSON (equivalent to SOUL.md)."""
    name = general["name"]
    personality = {}
    try:
        personality = json.loads(general["personality"]) if isinstance(general["personality"], str) else general["personality"]
    except (json.JSONDecodeError, TypeError):
        pass

    lines = [f"你是{name}，一位三国时代的武将。"]
    if personality.get("temperament"):
        lines.append(f"\n性格: {personality['temperament']}")
    if personality.get("battle_style"):
        lines.append(f"用兵风格: {personality['battle_style']}")
    if personality.get("risk_preference"):
        lines.append(f"风险偏好: {personality['risk_preference']}")
    if personality.get("lord_attitude"):
        lines.append(f"对主态度: {personality['lord_attitude']}")
    if personality.get("ally_attitude"):
        lines.append(f"对盟友: {personality['ally_attitude']}")
    if personality.get("enemy_attitude"):
        lines.append(f"对敌人: {personality['enemy_attitude']}")

    lines.append(f"\n数值:")
    lines.append(f"  武力: {general['war']}  统帅: {general['cmd']}  智力: {general['intel']}")
    lines.append(f"  政治: {general['politics']}  魅力: {general['charm']}")
    if general.get("loyalty") is not None:
        lines.append(f"  忠诚: {general['loyalty']}")
    lines.append(f"  兵力: {general['troops']}  粮草: {general['food']}日")

    if memory_summary:
        lines.append(f"\n近期记忆:\n{memory_summary}")

    lines.append("""
决策规则:
- 做决策时优先遵循你的人格与作风
- 粮草不足时战斗力下降
- 忠诚度低时可能抗命或叛变
- 根据局势和自身状态选择行动

输出格式: 严格JSON
{"action": "fight|retreat|negotiate|idle|rebel|advise|...", "effort": 0.0-1.0, "target": "...", "narrative": "..."}
""")
    return "\n".join(lines)


def general_decide(
    general: dict,
    context: dict,
    memory_summary: str = "",
    model: str | None = None,
) -> dict:
    """Ask a general to make a decision based on context and personality.

    Args:
        general: General dict from database (must include personality JSON).
        context: Situation dict describing the current event.
        memory_summary: Recent memory text to include in system prompt.

    Returns:
        Dict with action, effort, target, narrative keys.
    """
    system_prompt = _build_personality_prompt(general, memory_summary)
    user_message = json.dumps(context, ensure_ascii=False)
    return llm_call_json(system_prompt, user_message, model=model)


def trigger_autonomy(conn: sqlite3.Connection, general_id: str) -> dict:
    """Trigger autonomous decision for a single general."""
    general = get_general(conn, general_id)
    if general is None:
        return {"general": general_id, "status": "error", "error": "not found"}

    cursor = conn.execute("SELECT value FROM game_state WHERE key='current_day'")
    day_row = cursor.fetchone()
    current_day = int(day_row[0]) if day_row else 1
    cursor = conn.execute("SELECT value FROM game_state WHERE key='season'")
    season_row = cursor.fetchone()
    season = season_row[0] if season_row else "春"

    recent_memories = get_memories(conn, general_id, limit=5)
    memory_text = "\n".join(
        f"第{m['game_day']}日 [{m['event_type']}] {m['summary']}"
        for m in recent_memories
    )

    context = {
        "type": "autonomy_check",
        "current_day": current_day,
        "season": season,
        "your_status": {
            "troops": general["troops"],
            "food": general["food"],
            "loyalty": general["loyalty"],
        },
        "instruction": "Review your situation and decide what action to take. Consider your loyalty, troops, food supplies, and ambitions.",
    }

    decision = general_decide(general, context, memory_text)
    return {"general": general_id, "name": general["name"], "decision": decision}


def trigger_all_autonomy(conn: sqlite3.Connection) -> list[dict]:
    """Trigger autonomous decisions for all non-player generals."""
    cursor = conn.execute(
        "SELECT id FROM generals WHERE is_player=0"
    )
    results = []
    for row in cursor.fetchall():
        result = trigger_autonomy(conn, row[0])
        results.append(result)
    return results
```

- [ ] **Step 2: Verify import**

```bash
uv run python -c "from ai_war_game.autonomy import general_decide, trigger_autonomy; print('OK')"
```
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add src/ai_war_game/autonomy.py
git commit -m "feat: add general decision system (replaces agent_comm.py)"
```

---

### Task 8: Migrate `battle.py` — remove agent_comm dependency

**Files:**
- Create: `src/ai_war_game/battle.py`
- Reference: `hermes-skill/scripts/battle.py`

- [ ] **Step 1: Create `src/ai_war_game/battle.py`**

Copy from `hermes-skill/scripts/battle.py` with these changes:
- Remove `_import_agent_comm()` function entirely
- In `start_battle()`, replace `send_to_inbox/invoke_generals/collect_responses` with direct `general_decide()` calls
- Update imports to use `ai_war_game.db` and `ai_war_game.autonomy`
- Update `get_db_path()` usage

Key change in `start_battle()`:

```python
from ai_war_game.db import get_db_path, get_general
from ai_war_game.autonomy import general_decide


def start_battle(conn, queue_path, graph_path, attacker_id, defender_id, city_id) -> dict:
    participants = identify_participants(conn, attacker_id, defender_id)

    all_participant_ids = [attacker_id, defender_id]
    for ally in participants.get("attacker_allies", []):
        if ally["id"] not in all_participant_ids:
            all_participant_ids.append(ally["id"])
    for ally in participants.get("defender_allies", []):
        if ally["id"] not in all_participant_ids:
            all_participant_ids.append(ally["id"])

    decisions = {}
    for gid in all_participant_ids:
        side = "attacker" if (
            gid == attacker_id
            or gid in [a["id"] for a in participants["attacker_allies"]]
        ) else "defender"
        context = build_battle_context(participants, side, gid)
        general_data = get_general(conn, gid)
        if general_data:
            decisions[gid] = general_decide(general_data, json.loads(context))

    return {
        "participants": participants,
        "decisions": decisions,
    }
```

Keep all other functions (`identify_participants`, `build_battle_context`, `apply_battle_result`, `format_battle_report`, etc.) identical.

- [ ] **Step 2: Verify import**

```bash
uv run python -c "from ai_war_game.battle import start_battle, apply_battle_result, format_battle_report; print('OK')"
```
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add src/ai_war_game/battle.py
git commit -m "feat: migrate battle.py with in-process general decisions"
```

---

### Task 9: Migrate `init_scenario.py` — use llm.py instead of hermes_client

**Files:**
- Create: `src/ai_war_game/init_scenario.py`
- Reference: `hermes-skill/scripts/init_scenario.py`

- [ ] **Step 1: Create `src/ai_war_game/init_scenario.py`**

Changes from `hermes-skill/scripts/init_scenario.py`:
- Replace `from hermes_client import ...` → `from ai_war_game.llm import llm_call_json, LLMError`
- Remove `check_environment()` call (no Hermes to check)
- Remove `create_hermes_profile()` function entirely (no more Hermes profiles)
- Use `llm_call_json()` instead of `call_hermes()` + `parse_json_response()`
- Update `from db import ...` → `from ai_war_game.db import ...`
- Remove `_resolve_executable` reference

```python
"""init_scenario.py — LLM-based scenario generation and persistence."""

from __future__ import annotations

import json
import os
import sqlite3
from pathlib import Path

from ai_war_game.db import (
    add_triple,
    create_schema,
    get_graph_path,
    insert_city,
    insert_faction,
    insert_general,
    log_event,
    upsert_state,
)
from ai_war_game.llm import LLMError, llm_call_json


SCHEMA_HINT = json.dumps({
    "scenario": "str",
    "player_identity": {"id": "str", "display_name": "str", "faction_id": "str"},
    "factions": [{"id": "str", "name": "str"}],
    "cities": [{"id": "str", "name": "str", "x": "int", "y": "int", "terrain": "str", "owner": "str"}],
    "connections": [{"from": "str", "to": "str", "distance": "int"}],
    "generals": [{
        "id": "str", "name": "str",
        "war": "int", "command": "int", "intel": "int",
        "politics": "int", "charm": "int",
        "loyalty": "int|null", "troops": "int", "food": "int",
        "position": "str", "faction": "str", "is_player": "bool",
        "personality": {"temperament": "str", "battle_style": "str", "risk_preference": "str",
                        "lord_attitude": "str", "ally_attitude": "str", "enemy_attitude": "str"}
    }],
    "relationships": [{"subject": "str", "predicate": "str", "object": "str", "metadata": {}}],
    "initial_state": {"day": "int", "season": "str", "weather": "str"},
}, ensure_ascii=False)


SYSTEM_PROMPT = f"""You are a Three Kingdoms scenario generator.
Generate a complete game world as JSON given the theme and player's chosen general.

Validation rules:
- war/cmd/intel/politics/charm: 1-100
- loyalty: 1-100, must be null for is_player=true
- troops: 100-100000
- food: 1-365
- At least 3 cities, 5 generals
- Exactly one general with is_player=true
- All position/city references must be valid

Respond with valid JSON only following this schema:
{SCHEMA_HINT}"""


def generate_scenario(theme: str, player_name: str) -> dict:
    """Generate scenario via LLM and return parsed JSON."""
    user_message = f"Theme: {theme}\nPlayer's chosen identity: {player_name}"
    return llm_call_json(SYSTEM_PROMPT, user_message, json_schema_hint=SCHEMA_HINT)


def _extract_factions(data: dict) -> dict[str, str]:
    """Build faction_id → faction_name mapping."""
    faction_names = {}
    for f in data.get("factions", []):
        faction_names[f["id"]] = f["name"]
    for city in data.get("cities", []):
        if city["owner"] not in faction_names:
            faction_names[city["owner"]] = city["owner"]
    for general in data.get("generals", []):
        if general["faction"] not in faction_names:
            faction_names[general["faction"]] = general["faction"]
    if "player_identity" in data:
        fid = data["player_identity"]["faction_id"]
        if fid not in faction_names:
            faction_names[fid] = fid
    return faction_names


def _map_general_for_db(g: dict) -> dict:
    return {
        "id": g["id"],
        "name": g["name"],
        "war": g["war"],
        "cmd": g["command"],
        "intel": g["intel"],
        "politics": g["politics"],
        "charm": g["charm"],
        "loyalty": g.get("loyalty"),
        "troops": g["troops"],
        "food": g["food"],
        "position_city_id": g["position"],
        "faction_id": g["faction"],
        "is_player": g.get("is_player", False),
        "personality": json.dumps(g.get("personality", {}), ensure_ascii=False),
    }


def persist_scenario(db_path: str, scenario_data: dict) -> dict:
    """Persist generated scenario to SQLite + graph.json."""
    graph_path = get_graph_path(db_path)
    os.makedirs(os.path.dirname(db_path), exist_ok=True)

    conn = sqlite3.connect(db_path)
    try:
        create_schema(conn)

        factions = _extract_factions(scenario_data)
        for fid, fname in factions.items():
            insert_faction(conn, fid, fname)

        for city in scenario_data["cities"]:
            insert_city(conn, city["id"], city["name"], city["x"], city["y"], city["terrain"], city["owner"])

        for g in scenario_data["generals"]:
            insert_general(conn, _map_general_for_db(g))

        state = scenario_data.get("initial_state", {})
        upsert_state(conn, "current_day", str(state.get("day", 1)), 1)
        upsert_state(conn, "season", state.get("season", "春"), 1)
        upsert_state(conn, "weather", state.get("weather", "晴"), 1)
        upsert_state(conn, "scenario_name", scenario_data.get("scenario", ""), 1)
        upsert_state(conn, "player_identity", json.dumps(scenario_data.get("player_identity", {}), ensure_ascii=False), 1)

        log_event(conn, 1, 1, "scenario_start", scenario_data["player_identity"]["id"], None,
                  json.dumps({"scenario": scenario_data.get("scenario", ""), "theme": "auto"}, ensure_ascii=False))

        if graph_path and not os.path.isfile(graph_path):
            with open(graph_path, "w") as gf:
                json.dump([], gf)

        for conn_data in scenario_data.get("connections", []):
            add_triple(graph_path, conn_data["from"], "connects", conn_data["to"], {"distance": conn_data["distance"]})

        for rel in scenario_data.get("relationships", []):
            add_triple(graph_path, rel["subject"], rel["predicate"], rel["object"], rel.get("metadata", {}))
    finally:
        conn.close()

    return {
        "scenario": scenario_data.get("scenario"),
        "factions": list(factions.keys()),
        "cities": len(scenario_data.get("cities", [])),
        "generals": len(scenario_data.get("generals", [])),
        "player": scenario_data.get("player_identity", {}).get("display_name"),
        "db_path": db_path,
    }


def init_scenario(theme: str, player_name: str, db_path: str | None = None) -> dict:
    """Generate and persist a new game scenario in one call."""
    scenario_data = generate_scenario(theme, player_name)
    resolved_db = db_path or get_db_path(None)
    return persist_scenario(resolved_db, scenario_data)
```

- [ ] **Step 2: Verify import**

```bash
uv run python -c "from ai_war_game.init_scenario import init_scenario; print('OK')"
```
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add src/ai_war_game/init_scenario.py
git commit -m "feat: migrate init_scenario.py to use llm.py (removed hermes dependency)"
```

---

### Task 10: Create CLI entry point (`cli.py` + `__main__.py`)

**Files:**
- Create: `src/ai_war_game/cli.py`
- Create: `src/ai_war_game/__main__.py`

- [ ] **Step 1: Write `src/ai_war_game/cli.py`**

```python
"""cli.py — REPL entry point for AI War Game (replaces hermes chat + SKILL.md)."""

from __future__ import annotations

import sqlite3
import sys

from ai_war_game import db as war_db
from ai_war_game import view as war_view
from ai_war_game.engine import advance_time, get_event_queue_path
from ai_war_game.init_scenario import init_scenario
from ai_war_game.llm import LLMError, llm_call


GM_SYSTEM_PROMPT = """你是三国沙盘战争的 Game Master。
每次玩家下令的处理流程:
1. 识别命令类型并调用对应函数
2. 推进时间(time_engine advance)
3. 处理触发事件(战斗/粮草预警/到达)
4. 武将自主行为(autonomy trigger-all)
5. 展示结果(view show)

核心规则:
- 武/统/智/政/魅: 1-100, 忠: 1-100(玩家null)
- 粮草不足5天预警，不足2天危急
- 战斗由你综合数值、天气、地形、人格生成结果
- 中文输出，简洁为主"""


def show_help() -> str:
    return """可用命令:
  new-game --theme <主题> --player <武将名>  创建新局
  status / 查看局势                         查看当前局势
  general <id> / 查看武将 <id>              查看武将详情
  map / 查看地图                           查看地图
  events / 查看事件                        查看最近事件
  advance --days N / 推进 N 天              推进时间
  battle --attacker <id> --defender <id>   发动战斗
  help                                     显示帮助
  exit / quit                              退出"""


def _run_with_db(func, db_path: str, *args, **kwargs):
    conn = sqlite3.connect(db_path)
    try:
        return func(conn, *args, **kwargs)
    finally:
        conn.close()


def run_cli(argv: list[str] | None = None) -> int:
    db_path = war_db.get_db_path(None)
    print("【AI 沙盘战争】输入 'help' 查看命令")

    while True:
        try:
            cmd = input("⚔ ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break

        if not cmd:
            continue
        if cmd in ("exit", "quit", "q"):
            break
        if cmd == "help":
            print(show_help())
            continue

        # Command routing
        if cmd.startswith("new-game"):
            parts = cmd.split()
            try:
                theme_idx = parts.index("--theme") + 1
                player_idx = parts.index("--player") + 1
                theme = parts[theme_idx]
                player = parts[player_idx]
            except (ValueError, IndexError):
                print("用法: new-game --theme <主题> --player <武将名>")
                continue
            try:
                result = init_scenario(theme, player, db_path)
                print(f"世界生成完成: {result['scenario']}")
                print(f"  势力: {len(result['factions'])}  城池: {result['cities']}  武将: {result['generals']}")
            except LLMError as e:
                print(f"剧本生成失败: {e}")

        elif cmd in ("status", "查看局势"):
            conn = sqlite3.connect(db_path)
            try:
                cursor = conn.execute("SELECT value FROM game_state WHERE key='player_identity'")
                row = cursor.fetchone()
                if not row:
                    print("错误: 未找到玩家身份。先创建新局: new-game --theme ... --player ...")
                    continue
                player_id = row[0]
                general = war_db.get_general(conn, player_id)
                if not general:
                    print(f"错误: 未找到武将 {player_id}")
                    continue
                player_name = general["name"]
                faction_id = general["faction_id"]
                lines = war_view.format_show(conn, faction_id, player_id, player_name)
                print("\n".join(lines))
            finally:
                conn.close()

        elif cmd.startswith("general ") or cmd.startswith("查看武将"):
            parts = cmd.split()
            gid = parts[-1]
            lines = _run_with_db(war_view.format_general, db_path, gid)
            print("\n".join(lines))

        elif cmd in ("map", "查看地图"):
            lines = _run_with_db(war_view.format_map, db_path)
            print("\n".join(lines))

        elif cmd in ("events", "查看事件"):
            conn = sqlite3.connect(db_path)
            try:
                events = war_db.get_events(conn, limit=10)
                lines = war_view.format_events(events)
                print("\n".join(lines))
            finally:
                conn.close()

        elif cmd.startswith("advance") or cmd.startswith("推进"):
            # parse: "advance --days 5" or "推进 5 天"
            days = 1
            try:
                parts = cmd.split()
                if "--days" in parts:
                    days = int(parts[parts.index("--days") + 1])
                else:
                    for p in parts:
                        if p.isdigit():
                            days = int(p)
                            break
            except (ValueError, IndexError):
                pass
            queue_path = get_event_queue_path(db_path)
            graph_path = war_db.get_graph_path(db_path)
            conn = sqlite3.connect(db_path)
            try:
                events = advance_time(conn, queue_path, graph_path, days)
                print(f"推进了 {days} 天，触发 {len(events)} 个事件")
                if events:
                    for evt in events:
                        print(f"  第{evt['day']}日 [{evt['event_type']}]")
            finally:
                conn.close()

        elif cmd.startswith("battle") or cmd.startswith("攻击"):
            print("战斗系统: 正在开发中，请使用 'advance' 推进时间")

        else:
            # Unknown command → LLM fallback
            try:
                response = llm_call(GM_SYSTEM_PROMPT, cmd)
                print(response)
            except LLMError as e:
                print(f"无法理解命令: {e}")
                print("输入 'help' 查看可用命令")

    return 0
```

- [ ] **Step 2: Write `src/ai_war_game/__main__.py`**

```python
"""__main__.py — python -m ai_war_game entry point."""
from ai_war_game.cli import run_cli

if __name__ == "__main__":
    raise SystemExit(run_cli())
```

- [ ] **Step 3: Add CLI entry point to `pyproject.toml`**

```toml
[project.scripts]
ai-war-game = "ai_war_game.__main__:main"
```

But since `__main__.py` doesn't have a `main` function, let's be cleaner:

Update `src/ai_war_game/__main__.py`:
```python
"""__main__.py — python -m ai_war_game entry point."""
from ai_war_game.cli import run_cli

def main():
    raise SystemExit(run_cli())

if __name__ == "__main__":
    main()
```

And `pyproject.toml`:
```toml
[project.scripts]
ai-war-game = "ai_war_game.__main__:main"
```

- [ ] **Step 4: Verify entry works**

```bash
uv run python -m ai_war_game --help
```
Or just verify import:
```bash
uv run python -c "from ai_war_game.cli import run_cli; print('OK')"
```
Expected: `OK`

- [ ] **Step 5: Commit**

```bash
git add src/ai_war_game/cli.py src/ai_war_game/__main__.py
git commit -m "feat: add CLI entry point (replaces hermes chat + SKILL.md)"
```

---

### Task 11: Clean up Hermes files

**Files:**
- Delete: `hermes-skill/` (entire directory)
- Delete: `vendors/hermes-agent/` (git submodule)
- Delete: `tools/` (entire directory)
- Delete: `src/ai_war_game/interfaces/` (entire directory)
- Delete: `INSTALL.md`
- Delete: `tests/unit/hermes_skill/test_hermes_client.py`
- Modify: `README.md`, `AGENTS.md`, `pyproject.toml`

- [ ] **Step 1: Remove git submodule**

```bash
# Check if vendored as submodule
git submodule status vendors/hermes-agent 2>/dev/null || true
# If submodule, deinit and remove:
git submodule deinit -f vendors/hermes-agent 2>/dev/null || true
rm -rf vendors/hermes-agent
```

- [ ] **Step 2: Delete other Hermes artifacts**

```bash
rm -rf hermes-skill
rm -rf tools
rm -rf src/ai_war_game/interfaces
rm -f INSTALL.md
rm -f tests/unit/hermes_skill/test_hermes_client.py
```

- [ ] **Step 3: Update `README.md`**

```markdown
# AI War Game

AI 驱动的沙盘战争游戏。每位武将是独立 AI Agent，拥有独立人格与记忆。

## Quick Start

```bash
# 1. 安装依赖
uv sync

# 2. 配置 LLM
export AI_WAR_GAME_LLM_MODEL="openai/gpt-4o-mini"
export AI_WAR_GAME_LLM_API_KEY="sk-..."

# 3. 开始游戏
uv run python -m ai_war_game
```

## 命令

```bash
uv run python -m ai_war_game    # 启动游戏
uv run python -m ai_war_game --help
uv run pytest                    # 运行测试
uv run ruff check .             # Lint
uv run ruff format .            # Format
```

## 环境变量

| 变量 | 必填 | 含义 |
|---|---|---|
| `AI_WAR_GAME_LLM_MODEL` | 否 | LLM 模型标识 (默认 openai/gpt-4o-mini) |
| `AI_WAR_GAME_LLM_API_KEY` | 否 | API key (也支持标准 OPENAI_API_KEY) |
| `AI_WAR_GAME_LLM_API_BASE` | 否 | 自定义 API base URL |

支持 litellm 所有格式: `openai/gpt-4`, `anthropic/claude-sonnet-4`, `ollama/llama3` 等。

## 架构

```
玩家输入
  │
  ├── CLI (src/ai_war_game/cli.py)
  │     命令路由规则 → Python 函数直接调用
  │     无法识别的命令 → LLM fallback
  │
  ├── 核心模块
  │     db.py      — SQLite 数据库层
  │     view.py    — 展示格式化
  │     engine.py  — 时间推进 + 事件队列
  │     battle.py  — 战斗结算
  │     autonomy.py — 武将 LLM 决策
  │
  └── LLM 层 (litellm)
        llm.py — 统一 LLM 调用接口
```

## 开发

```bash
uv run pytest                # 运行全部测试
uv run ruff check .          # Lint
uv run ruff format .         # Format
```
```

- [ ] **Step 4: Update `AGENTS.md`**

```markdown
# AGENTS.md

## Project Status

全阶段实现完成。自包含 Python 沙盘战争游戏，无外部 Agent 依赖。

- CLI 入口 (`uv run python -m ai_war_game`)
- 建局、推进时间、战斗、武将自主行为均已实现
- Game design spec in `docs/superpowers/specs/`

## Tech Stack

- Language: Python 3.12+
- Package manager: [uv](https://docs.astral.sh/uv/)
- LLM: [litellm](https://github.com/BerriAI/litellm) (OpenAI/Claude/Ollama 等 100+ 模型)
- Storage: SQLite (stdlib `sqlite3`) + JSON graph triple store

## Commands

```bash
uv run python -m ai_war_game    # 启动游戏
uv run pytest                    # Run tests
uv run ruff check .              # Lint
uv run ruff format .             # Format
```

## Architecture

```
src/ai_war_game/
├── __init__.py
├── __main__.py            # python -m 入口
├── cli.py                 # REPL 循环 + 命令路由
├── llm.py                 # litellm LLM 封装
├── db.py                  # SQLite 数据库层
├── view.py                # 展示格式化
├── engine.py              # 时间推进 + 事件队列
├── battle.py              # 战斗系统
├── autonomy.py            # 武将自主决策
├── init_scenario.py       # LLM 剧本生成
└── models.py              # 数据类

data/
├── game.db                # SQLite 数据库
└── graph.json             # 三元组存储 (城池连接 + 关系)
```

### 数据流

```
玩家 (CLI)
  │
  ├── cli.py 识别命令
  │     规则路由 (str.startswith) + LLM fallback
  │
  ├── Python 函数直接调用
  │     db.py           — 数据库 CRUD
  │     view.py         — 展示格式化
  │     engine.py       — 推进时间、处理事件
  │     battle.py       — 战斗编排
  │     autonomy.py     — 武将自主决策 (同进程 LLM 调用)
  │
  └── llm.py (litellm)
        init_scenario — 剧本生成
        general_decide — 武将决策
```

### 游戏循环

1. 玩家下令 → CLI 识别命令类型
2. 推进时间 (`engine.advance`)
3. 处理触发事件（战斗、粮草预警、到达等）
4. 武将自主行为 (`autonomy.trigger_all_autonomy`)
5. 展示结果 (`view.format_show`)
```

- [ ] **Step 5: Update `pyproject.toml` — remove hermes-skill from pythonpath**

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "-ra"
pythonpath = ["src"]

[tool.ruff]
line-length = 100
target-version = "py312"
src = ["src", "tests"]
```

- [ ] **Step 6: Update `.gitignore` and clean up**

```bash
# Remove .gitmodules if venidors/hermes-agent was the only submodule
git rm .gitmodules 2>/dev/null || true
```

- [ ] **Step 7: Remove empty directories**

```bash
# Clean up now-empty test subdirectories if all tests are gone
rmdir tests/unit/hermes_skill 2>/dev/null || true
```

- [ ] **Step 8: Commit**

```bash
git add -A
git commit -m "cleanup: remove Hermes Agent files, update docs and config"
```

---

### Task 12: Update tests + full verification

**Files:**
- Modify: `tests/unit/hermes_skill/test_init_scenario.py`
- Modify: `tests/unit/hermes_skill/test_battle.py`
- Modify: `tests/unit/hermes_skill/test_autonomy.py` (if exists)
- Delete: `tests/unit/hermes_skill/test_agent_comm.py`
- Create: `tests/unit/test_cli.py`
- Verify: all existing tests pass

- [ ] **Step 1: Update test imports**

Update `tests/unit/hermes_skill/test_db.py` — change import from:
```python
from db import ...
```
to:
```python
from ai_war_game.db import ...
```

Update `tests/unit/hermes_skill/test_view.py` — same pattern.

Update `tests/unit/hermes_skill/test_time_engine.py` — same pattern.

- [ ] **Step 2: Update `tests/unit/hermes_skill/test_battle.py`**

Replace imports that reference `agent_comm` with mocks of `ai_war_game.autonomy.general_decide`.

- [ ] **Step 3: Remove or rewrite `test_agent_comm.py`**

Remove it entirely (agent_comm.py is deleted). The `general_decide` logic is tested via test_autonomy or test_llm.

- [ ] **Step 4: Write `tests/unit/test_cli.py`**

```python
"""tests/unit/test_cli.py"""

from ai_war_game.cli import show_help


def test_show_help_contains_key_commands():
    help_text = show_help()
    assert "new-game" in help_text
    assert "status" in help_text
    assert "help" in help_text
```

- [ ] **Step 5: Run all tests**

```bash
uv run pytest -v 2>&1 | head -100
```

Expected: All existing tests pass (adjusting for removed/moved files). If any test failures, fix the import paths and mocking.

- [ ] **Step 6: Run linter**

```bash
uv run ruff check .
uv run ruff format . --check
```

Expected: Clean

- [ ] **Step 7: Final commit**

```bash
git add -A
git commit -m "test: update tests for Hermes-free architecture"
```

---

## Spec Coverage Check

| Spec Requirement | Task |
|---|---|
| LLM abstraction (llm.py with litellm) | Task 1 |
| Package scaffolding + models | Task 2 |
| db.py migration to library module | Task 3 |
| view.py migration to library module | Task 4 |
| time_engine → engine.py migration | Task 5 |
| general_memories table + CRUD | Task 6 |
| General decision system (replaces agent_comm) | Task 7 |
| battle.py migration (no agent_comm) | Task 8 |
| init_scenario.py migration (no hermes_client) | Task 9 |
| CLI entry point (replaces hermes chat + SKILL.md) | Task 10 |
| Delete Hermes files, update docs | Task 11 |
| Update tests + verification | Task 12 |

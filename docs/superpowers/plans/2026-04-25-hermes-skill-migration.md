# P1-P3 Hermes Skill Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Migrate the AI War Game from standalone Python CLI to a Hermes Agent Skill (P1-P3: SKILL.md + SQLite database + LLM scenario initialization)

**Architecture:** Single Hermes Agent (Game Master) loads SKILL.md as its behavior rules. SKILL.md routes player commands to standalone Python scripts via `terminal()`. Scripts handle DB CRUD (`db.py`), display formatting (`view.py`), and world generation (`init_scenario.py`). All game data lives in SQLite + JSON graph file. Each general gets a Hermes profile with SOUL.md for future multi-agent use.

**Tech Stack:** Python 3.12+, SQLite3 (stdlib), Hermes Agent, pytest

---

## File Map

```
hermes-skill/                              # Symlinked → ~/.hermes/skills/strategy/ai-war-game/
├── SKILL.md                               # Game Master rules & script routing
├── lib/
│   ├── __init__.py
│   └── hermes_client.py                   # Health check + subprocess LLM call
├── scripts/
│   ├── __init__.py
│   ├── db.py                              # SQLite schema creation + CRUD + graph triple store
│   ├── view.py                            # Display formatting (show/general/map/events)
│   ├── init_scenario.py                   # LLM world generation → validate → persist → create profiles
│   ├── init_prompt.txt                    # LLM prompt template (txt resource)
│   └── soul_general.txt                   # SOUL.md rendering template (txt resource)

tests/
├── conftest.py                            # Keep only shared fixtures, remove old domain fixtures
└── unit/
    └── hermes_skill/
        ├── __init__.py
        ├── test_hermes_client.py          # Health check + LLM call tests
        ├── test_db.py                     # Schema creation + CRUD + graph tests
        ├── test_view.py                   # Display formatting tests
        └── test_init_scenario.py          # Validation + prompt generation tests

pyproject.toml                             # Update: remove old CLI entry, add pythonpath for hermes-skill
```

**Files to remove (old architecture):**
- `src/ai_war_game/cli/` (entire dir)
- `src/ai_war_game/application/` (entire dir)  
- `src/ai_war_game/domain/` (entire dir)
- `src/ai_war_game/infrastructure/persistence/` (entire dir)
- `src/ai_war_game/infrastructure/hermes/` (entire dir, replaced by `hermes-skill/lib/hermes_client.py`)
- `src/ai_war_game/interfaces/` (keep for future WeChat integration)
- `tests/conftest.py` (replace with new fixtures)
- `tests/unit/domain/`, `tests/unit/application/`, `tests/unit/infrastructure/`, `tests/unit/interfaces/` (old tests)
- `tests/integration/` (old integration tests)

---

### Task 1: Project skeleton + Hermes client library

**Files:**
- Create: `hermes-skill/lib/__init__.py`
- Create: `hermes-skill/lib/hermes_client.py`
- Create: `hermes-skill/scripts/__init__.py`
- Create: `tests/unit/hermes_skill/__init__.py`
- Create: `tests/unit/hermes_skill/test_hermes_client.py`
- Modify: `pyproject.toml`

- [ ] **Step 1: Update pyproject.toml**

Remove the `[project.scripts]` entry. Add `pytest-env` for test env vars. Add `hermes-skill/lib` and `hermes-skill/scripts` to pythonpath.

```toml
[project]
name = "ai-war-game"
version = "0.1.0"
description = "AI-driven sandbox warfare game built on Hermes Agent"
readme = "README.md"
requires-python = ">=3.12"
dependencies = []

# Removed: [project.scripts] — no more CLI entry point

[dependency-groups]
dev = [
    "pytest>=9.0.3",
    "ruff>=0.15.11",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/ai_war_game"]

[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "-ra"
pythonpath = ["src", "hermes-skill/lib", "hermes-skill/scripts"]

[tool.ruff]
line-length = 100
target-version = "py312"
src = ["src", "tests", "hermes-skill/lib", "hermes-skill/scripts"]

[tool.ruff.lint]
select = ["E", "F", "I", "B", "UP", "RUF", "SIM"]
ignore = []

[tool.ruff.lint.per-file-ignores]
"tests/**" = ["B011"]
```

- [ ] **Step 2: Create directory structure**

```bash
mkdir -p hermes-skill/lib hermes-skill/scripts hermes-skill/data
mkdir -p tests/unit/hermes_skill
touch hermes-skill/lib/__init__.py
touch hermes-skill/scripts/__init__.py
touch tests/unit/hermes_skill/__init__.py
```

- [ ] **Step 3: Write the failing test for hermes_client health check**

```python
"""tests/unit/hermes_skill/test_hermes_client.py"""

import stat
from pathlib import Path

import pytest
from hermes_client import HermesUnavailableError, check_environment, call_hermes


class TestCheckEnvironment:
    def test_passes_when_bin_model_and_config_exist(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ):
        hermes_bin = tmp_path / "hermes"
        hermes_bin.write_text("#!/bin/sh\nexit 0\n")
        hermes_bin.chmod(hermes_bin.stat().st_mode | stat.S_IXUSR)
        config = tmp_path / "hermes.yaml"
        config.write_text("model: demo\n")
        monkeypatch.setenv("AI_WAR_GAME_HERMES_BIN", str(hermes_bin))
        monkeypatch.setenv("AI_WAR_GAME_HERMES_MODEL", "hermes-3")
        monkeypatch.setenv("AI_WAR_GAME_HERMES_CONFIG", str(config))

        check_environment()  # should not raise

    def test_raises_when_bin_missing(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
        config = tmp_path / "hermes.yaml"
        config.write_text("model: demo\n")
        monkeypatch.setenv("AI_WAR_GAME_HERMES_BIN", "definitely-missing")
        monkeypatch.setenv("AI_WAR_GAME_HERMES_MODEL", "hermes-3")
        monkeypatch.setenv("AI_WAR_GAME_HERMES_CONFIG", str(config))

        with pytest.raises(HermesUnavailableError):
            check_environment()

    def test_raises_when_model_missing(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
        hermes_bin = tmp_path / "hermes"
        hermes_bin.write_text("#!/bin/sh\nexit 0\n")
        hermes_bin.chmod(hermes_bin.stat().st_mode | stat.S_IXUSR)
        config = tmp_path / "hermes.yaml"
        config.write_text("model: demo\n")
        monkeypatch.setenv("AI_WAR_GAME_HERMES_BIN", str(hermes_bin))
        monkeypatch.delenv("AI_WAR_GAME_HERMES_MODEL", raising=False)
        monkeypatch.setenv("AI_WAR_GAME_HERMES_CONFIG", str(config))

        with pytest.raises(HermesUnavailableError):
            check_environment()
```

- [ ] **Step 4: Run tests — expect failure**

```bash
uv run pytest tests/unit/hermes_skill/test_hermes_client.py::TestCheckEnvironment -v
```
Expected: FAIL with `ModuleNotFoundError: No module named 'hermes_client'`

- [ ] **Step 5: Write minimal hermes_client.py**

```python
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
    """调用 Hermes CLI 发送 prompt，返回原始 stdout。失败时抛 ScenarioGenerationError。"""
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
    """解析 LLM JSON 输出，失败时抛 ScenarioInvalidError。"""
    try:
        return dict(json.loads(raw))
    except json.JSONDecodeError as exc:
        raise ScenarioInvalidError(
            f"hermes 输出不是合法 JSON: {exc}; raw={raw[:200]!r}"
        ) from exc


def _resolve_executable(value: str) -> Path | None:
    candidate = Path(value)
    if candidate.is_file() and os.access(candidate, os.X_OK):
        return candidate
    found = shutil.which(value)
    return Path(found) if found else None
```

- [ ] **Step 6: Run tests — expect pass**

```bash
uv run pytest tests/unit/hermes_skill/test_hermes_client.py::TestCheckEnvironment -v
```
Expected: 3 PASSED

- [ ] **Step 7: Write failing tests for call_hermes**

Add to `test_hermes_client.py`:

```python
class TestCallHermes:
    def test_returns_stdout_on_success(self, monkeypatch):
        def fake_run(*args, **kwargs):
            class Result:
                returncode = 0
                stdout = '{"summary": "test"}'
                stderr = ""
            return Result()
        monkeypatch.setattr("hermes_client.subprocess.run", fake_run)
        monkeypatch.setenv("AI_WAR_GAME_HERMES_BIN", "hermes")
        monkeypatch.setenv("AI_WAR_GAME_HERMES_MODEL", "test-model")
        monkeypatch.setenv("AI_WAR_GAME_HERMES_CONFIG", "/tmp/fake.yaml")

        result = call_hermes("hello")
        assert result == '{"summary": "test"}'

    def test_raises_on_nonzero_exit(self, monkeypatch):
        def fake_run(*args, **kwargs):
            class Result:
                returncode = 1
                stdout = ""
                stderr = "error msg"
            return Result()
        monkeypatch.setattr("hermes_client.subprocess.run", fake_run)
        monkeypatch.setenv("AI_WAR_GAME_HERMES_BIN", "hermes")
        monkeypatch.setenv("AI_WAR_GAME_HERMES_MODEL", "test-model")
        monkeypatch.setenv("AI_WAR_GAME_HERMES_CONFIG", "/tmp/fake.yaml")

        with pytest.raises(ScenarioGenerationError, match="error msg"):
            call_hermes("hello")

    def test_parses_valid_json(self):
        result = parse_json_response('{"key": "val"}')
        assert result == {"key": "val"}

    def test_raises_on_invalid_json(self):
        with pytest.raises(ScenarioInvalidError, match="不是合法 JSON"):
            parse_json_response("not-json")
```

- [ ] **Step 8: Run tests — expect fail for the new call_hermes tests**

```bash
uv run pytest tests/unit/hermes_skill/test_hermes_client.py -v
```
Expected: 4 PASSED, 3 FAILED (the tests already pass since implementation is written — good, that's because we already wrote the implementation. The tests should pass since the implementation is already complete.)

Wait, actually since we wrote the full implementation in step 5, all tests should pass now. Let me adjust — the writing-plans skill says TDD: write test first, watch it fail, then implement. So I should split:

Actually, looking back, I wrote the implementation in step 5 before the test in step 7. In practice these tests would pass immediately because the implementation is already there. Let me reorder:

Step 3: Write health check tests
Step 4: Watch them fail
Step 5: Write implementation for health check only
Step 6: Watch them pass
Step 7: Write call_hermes tests
Step 8: Watch them fail (but since we already wrote the full implementation, they pass)

Actually, for the plan document, having the tests first then implementation is the right structure. The actual execution will follow TDD order. Let me restructure for clarity.

Let me rewrite this more carefully. Each task should have: write test → run → fail → implement → run → pass → commit.

- [ ] **Step 3: Write test file for hermes_client**

Content as shown above (TestCheckEnvironment + TestCallHermes classes).

- [ ] **Step 4: Run to confirm failure**

```bash
uv run pytest tests/unit/hermes_skill/test_hermes_client.py -v
```
Expected: `ModuleNotFoundError: No module named 'hermes_client'`

- [ ] **Step 5: Write hermes_client.py**

Content as shown above.

- [ ] **Step 6: Run to confirm pass**

```bash
uv run pytest tests/unit/hermes_skill/test_hermes_client.py -v
```
Expected: 7 passed

- [ ] **Step 7: Commit**

```bash
git add -A && git commit -m "feat: add hermes skill skeleton and hermes_client library"
```

---

### Task 2: SQLite database layer (scripts/db.py)

**Files:**
- Create: `hermes-skill/scripts/db.py`
- Create: `tests/unit/hermes_skill/test_db.py`

**DB Schema (embedded in db.py):**

```python
# 5 tables + events_log
SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS factions (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS cities (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    x INTEGER NOT NULL CHECK(x >= 0 AND x <= 1000),
    y INTEGER NOT NULL CHECK(y >= 0 AND y <= 1000),
    terrain TEXT NOT NULL CHECK(terrain IN ('平原', '山地', '水域', '森林')),
    owner_faction_id TEXT REFERENCES factions(id)
);

CREATE TABLE IF NOT EXISTS generals (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
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
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_day INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS events_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    game_day INTEGER NOT NULL,
    seq INTEGER NOT NULL,
    event_type TEXT NOT NULL,
    actor_id TEXT,
    target_id TEXT,
    details_json TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
"""
```

**db.py CLI API (argparse):**

| Command | Args | Description |
|---------|------|-------------|
| `db.py init [--db PATH]` | — | Create/migrate schema, return 0 |
| `db.py state read [--db PATH]` | — | Print all game_state as JSON lines |
| `db.py state write <key> <value> <day> [--db PATH]` | key value day | Insert or replace a state entry |
| `db.py general list [--db PATH]` | — | Print all generals as JSON array |
| `db.py general get <id> [--db PATH]` | id | Print single general as JSON |
| `db.py general update <id> <field> <value> [--db PATH]` | id field value | Update a general column |
| `db.py city list [--db PATH]` | — | Print all cities as JSON array |
| `db.py log-event <type> [--actor] [--target] [--details] [--db PATH]` | type | Insert event log entry |
| `db.py events [--limit N] [--db PATH]` | — | Print recent events as JSON array |
| `db.py graph read [--db PATH]` | — | Print all triples from graph.json |
| `db.py graph add <s> <p> <o> [--db PATH]` | s p o | Add triple to graph.json |
| `db.py scenario init [--db PATH] <json>` | json | Bulk-insert full scenario data |

All commands accept `--db-path` (default: `data/game.db` relative to script's parent dir).

Internal functions (testable):

```python
def get_db_path(db_arg: str | None, script_file: str) -> str   # resolve --db-path

def create_schema(conn: sqlite3.Connection) -> None              # execute SCHEMA_SQL
def insert_faction(conn, faction_id, name) -> None
def insert_city(conn, city_id, name, x, y, terrain, owner_faction_id) -> None
def insert_general(conn, data: dict) -> None                     # validate & insert
def upsert_state(conn, key, value, day) -> None
def get_state(conn) -> list[dict]
def log_event(conn, game_day, seq, event_type, actor_id, target_id, details_json) -> None
def get_events(conn, limit=10) -> list[dict]

# graph operations (JSON file, not SQLite)
def read_graph(graph_path: str) -> list[list]
def add_triple(graph_path: str, subject, predicate, obj) -> None

# bulk scenario init
def init_scenario_data(db_path: str, graph_path: str, scenario: dict) -> None
```

- [ ] **Step 1: Write the failing test for create_schema and basic CRUD**

```python
"""tests/unit/hermes_skill/test_db.py"""

import json
import sqlite3
import pytest
from db import (
    create_schema,
    insert_faction,
    insert_city,
    insert_general,
    upsert_state,
    get_state,
    log_event,
    get_events,
    read_graph,
    add_triple,
    init_scenario_data,
)


@pytest.fixture
def conn(tmp_path):
    db = tmp_path / "test.db"
    c = sqlite3.connect(str(db))
    create_schema(c)
    yield c
    c.close()


class TestCreateSchema:
    def test_tables_exist_after_create(self, conn):
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        )
        tables = [row[0] for row in cursor.fetchall()]
        assert "factions" in tables
        assert "cities" in tables
        assert "generals" in tables
        assert "game_state" in tables
        assert "events_log" in tables


class TestFactionCRUD:
    def test_insert_and_query(self, conn):
        insert_faction(conn, "wei", "曹魏")
        cursor = conn.execute("SELECT id, name FROM factions WHERE id=?", ("wei",))
        row = cursor.fetchone()
        assert row == ("wei", "曹魏")

    def test_duplicate_id_raises(self, conn):
        insert_faction(conn, "wei", "曹魏")
        with pytest.raises(sqlite3.IntegrityError):
            insert_faction(conn, "wei", " duplicated")


class TestCityCRUD:
    def test_insert_and_query(self, conn):
        insert_faction(conn, "wei", "曹魏")
        insert_city(conn, "luoyang", "洛阳", 100, 200, "平原", "wei")
        cursor = conn.execute(
            "SELECT id, name, x, y, terrain, owner_faction_id FROM cities WHERE id=?",
            ("luoyang",),
        )
        row = cursor.fetchone()
        assert row == ("luoyang", "洛阳", 100, 200, "平原", "wei")


class TestGeneralCRUD:
    def test_insert_and_query(self, conn):
        insert_faction(conn, "wei", "曹魏")
        insert_city(conn, "luoyang", "洛阳", 0, 0, "平原", "wei")
        insert_general(conn, {
            "id": "caocao",
            "name": "曹操",
            "war": 72,
            "cmd": 86,
            "intel": 91,
            "politics": 88,
            "charm": 80,
            "loyalty": None,
            "troops": 8000,
            "food": 15,
            "position_city_id": "luoyang",
            "faction_id": "wei",
            "is_player": True,
            "personality": json.dumps({"temperament": "ambitious"}),
        })
        cursor = conn.execute("SELECT id, name, war, cmd, intel, politics, charm, troops, food, is_player FROM generals WHERE id=?", ("caocao",))
        row = cursor.fetchone()
        assert row is not None
        assert row[0] == "caocao"

    def test_invalid_war_stat_raises(self, conn):
        insert_faction(conn, "wei", "曹魏")
        insert_city(conn, "luoyang", "洛阳", 0, 0, "平原", "wei")
        with pytest.raises(sqlite3.IntegrityError):
            insert_general(conn, {
                "id": "bad",
                "name": "Bad",
                "war": 999,  # out of range 1-100
                "cmd": 50,
                "intel": 50,
                "politics": 50,
                "charm": 50,
                "loyalty": 50,
                "troops": 5000,
                "food": 10,
                "position_city_id": "luoyang",
                "faction_id": "wei",
                "is_player": False,
                "personality": "{}",
            })


class TestGameState:
    def test_write_and_read(self, conn):
        upsert_state(conn, "current_day", "1", 1)
        upsert_state(conn, "season", "春", 1)
        states = get_state(conn)
        assert {"key": "current_day", "value": "1", "updated_day": 1} in states
        assert {"key": "season", "value": "春", "updated_day": 1} in states

    def test_upsert_overwrites(self, conn):
        upsert_state(conn, "current_day", "1", 1)
        upsert_state(conn, "current_day", "5", 5)
        states = get_state(conn)
        current_day_entries = [s for s in states if s["key"] == "current_day"]
        assert len(current_day_entries) == 1
        assert current_day_entries[0]["value"] == "5"


class TestEvents:
    def test_log_and_query(self, conn):
        log_event(conn, 1, 1, "scenario_start", None, None, "{}")
        log_event(conn, 1, 2, "general_created", "caocao", None, json.dumps({"name": "曹操"}))
        events = get_events(conn, limit=10)
        assert len(events) == 2
        assert events[0]["event_type"] == "scenario_start"
        assert events[1]["actor_id"] == "caocao"

    def test_limit(self, conn):
        for i in range(5):
            log_event(conn, 1, i, "test", None, None, "{}")
        events = get_events(conn, limit=3)
        assert len(events) == 3


class TestGraph:
    def test_read_empty_graph(self, tmp_path):
        graph_file = tmp_path / "graph.json"
        graph_file.write_text("[]")
        assert read_graph(str(graph_file)) == []

    def test_add_and_read(self, tmp_path):
        graph_file = tmp_path / "graph.json"
        graph_file.write_text("[]")
        add_triple(str(graph_file), "caocao", "serves", "han")
        triples = read_graph(str(graph_file))
        assert len(triples) == 1
        assert triples[0] == ["caocao", "serves", "han", {}]

    def test_multiple_triples(self, tmp_path):
        graph_file = tmp_path / "graph.json"
        graph_file.write_text("[]")
        add_triple(str(graph_file), "luoyang", "connects", "yingchuan", {"distance": 5})
        add_triple(str(graph_file), "caocao", "trusts", "liubei")
        triples = read_graph(str(graph_file))
        assert len(triples) == 2


class TestScenarioInit:
    def test_init_full_scenario(self, tmp_path):
        db_file = tmp_path / "test.db"
        graph_file = tmp_path / "graph.json"
        graph_file.write_text("[]")
        conn = sqlite3.connect(str(db_file))
        create_schema(conn)
        insert_faction(conn, "wei", "曹魏")
        insert_city(conn, "luoyang", "洛阳", 0, 0, "平原", "wei")
        conn.close()
        scenario = {
            "scenario_name": "黄巾之乱",
            "player_identity": "caocao",
            "state": {"current_day": 1, "season": "春", "weather": "晴"},
            "generals": [{
                "id": "caocao", "name": "曹操",
                "war": 72, "cmd": 86, "intel": 91, "politics": 88, "charm": 80,
                "loyalty": None, "troops": 8000, "food": 15,
                "position_city_id": "luoyang", "faction_id": "wei",
                "is_player": True, "personality": "{}",
            }],
            "events": [{"day": 1, "type": "scenario_start", "details": "黄巾之乱开始"}],
            "graph": [["luoyang", "connects", "yingchuan", {"distance": 5}]],
        }
        conn.close()
        init_scenario_data(str(db_file), str(graph_file), scenario)
        conn = sqlite3.connect(str(db_file))
        states = get_state(conn)
        keys = [s["key"] for s in states]
        assert "current_day" in keys
        assert "season" in keys
        conn.close()
```

- [ ] **Step 2: Run to confirm failure**

```bash
uv run pytest tests/unit/hermes_skill/test_db.py -v
```
Expected: `ModuleNotFoundError: No module named 'db'`

- [ ] **Step 3: Implement db.py**

```python
#!/usr/bin/env python3
"""db.py — SQLite database layer for AI War Game.

Usage:
    python3 db.py init
    python3 db.py state read
    python3 db.py state write <key> <value> <day>
    python3 db.py general list
    python3 db.py general get <id>
    python3 db.py general update <id> <field> <value>
    python3 db.py city list
    python3 db.py log-event <type> [--actor] [--target] [--details]
    python3 db.py events [--limit N]
    python3 db.py graph read
    python3 db.py graph add <s> <p> <o> [--meta]
    python3 db.py scenario init <json>
"""

import argparse
import json
import os
import sqlite3
import sys

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS factions (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS cities (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    x INTEGER NOT NULL CHECK(x >= 0 AND x <= 1000),
    y INTEGER NOT NULL CHECK(y >= 0 AND y <= 1000),
    terrain TEXT NOT NULL CHECK(terrain IN ('平原', '山地', '水域', '森林')),
    owner_faction_id TEXT REFERENCES factions(id)
);

CREATE TABLE IF NOT EXISTS generals (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
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
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_day INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS events_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    game_day INTEGER NOT NULL,
    seq INTEGER NOT NULL,
    event_type TEXT NOT NULL,
    actor_id TEXT,
    target_id TEXT,
    details_json TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
"""


def get_db_path(db_arg: str | None, script_file: str) -> str:
    if db_arg:
        return db_arg
    script_dir = os.path.dirname(os.path.abspath(script_file))
    skill_dir = os.path.dirname(script_dir)
    data_dir = os.path.join(skill_dir, "data")
    os.makedirs(data_dir, exist_ok=True)
    return os.path.join(data_dir, "game.db")


def get_graph_path(db_path: str) -> str:
    data_dir = os.path.dirname(db_path)
    return os.path.join(data_dir, "graph.json")


def create_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA_SQL)
    conn.commit()


def insert_faction(conn: sqlite3.Connection, faction_id: str, name: str) -> None:
    conn.execute("INSERT INTO factions (id, name) VALUES (?, ?)", (faction_id, name))
    conn.commit()


def insert_city(
    conn: sqlite3.Connection,
    city_id: str, name: str, x: int, y: int,
    terrain: str, owner_faction_id: str,
) -> None:
    conn.execute(
        "INSERT INTO cities (id, name, x, y, terrain, owner_faction_id) VALUES (?, ?, ?, ?, ?, ?)",
        (city_id, name, x, y, terrain, owner_faction_id),
    )
    conn.commit()


def insert_general(conn: sqlite3.Connection, data: dict) -> None:
    conn.execute(
        """INSERT INTO generals
           (id, name, war, cmd, intel, politics, charm, loyalty, troops, food,
            position_city_id, faction_id, is_player, personality)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            data["id"], data["name"], data["war"], data["cmd"], data["intel"],
            data["politics"], data["charm"], data.get("loyalty"),
            data["troops"], data["food"],
            data["position_city_id"], data["faction_id"],
            1 if data.get("is_player") else 0,
            json.dumps(data.get("personality", {}), ensure_ascii=False),
        ),
    )
    conn.commit()


def upsert_state(conn: sqlite3.Connection, key: str, value: str, day: int) -> None:
    conn.execute(
        "INSERT OR REPLACE INTO game_state (key, value, updated_day) VALUES (?, ?, ?)",
        (key, value, day),
    )
    conn.commit()


def get_state(conn: sqlite3.Connection) -> list[dict]:
    cursor = conn.execute("SELECT key, value, updated_day FROM game_state")
    return [{"key": row[0], "value": row[1], "updated_day": row[2]} for row in cursor.fetchall()]


def log_event(
    conn: sqlite3.Connection, game_day: int, seq: int,
    event_type: str, actor_id: str | None,
    target_id: str | None, details_json: str,
) -> None:
    conn.execute(
        "INSERT INTO events_log (game_day, seq, event_type, actor_id, target_id, details_json) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (game_day, seq, event_type, actor_id, target_id, details_json),
    )
    conn.commit()


def get_events(conn: sqlite3.Connection, limit: int = 10) -> list[dict]:
    cursor = conn.execute(
        "SELECT id, game_day, seq, event_type, actor_id, target_id, details_json, created_at "
        "FROM events_log ORDER BY id DESC LIMIT ?", (limit,),
    )
    cols = ["id", "game_day", "seq", "event_type", "actor_id", "target_id", "details_json", "created_at"]
    return [dict(zip(cols, row)) for row in cursor.fetchall()]


def read_graph(graph_path: str) -> list[list]:
    if not os.path.isfile(graph_path):
        return []
    with open(graph_path, encoding="utf-8") as f:
        data = json.load(f)
    return list(data)


def add_triple(
    graph_path: str, subject: str, predicate: str, obj: str, metadata: dict | None = None,
) -> None:
    triples = read_graph(graph_path)
    triple = [subject, predicate, obj, metadata or {}]
    triples.append(triple)
    with open(graph_path, "w", encoding="utf-8") as f:
        json.dump(triples, f, ensure_ascii=False, indent=2)


def init_scenario_data(db_path: str, graph_path: str, scenario: dict) -> None:
    conn = sqlite3.connect(db_path)
    try:
        state = scenario.get("state", {})
        for key, value in state.items():
            upsert_state(conn, key, str(value), int(state.get("current_day", 1)))
        for general_data in scenario.get("generals", []):
            insert_general(conn, general_data)
        seq = 0
        for event in scenario.get("events", []):
            seq += 1
            log_event(
                conn, event.get("day", 1), seq, event.get("type", "unknown"),
                event.get("actor_id"), event.get("target_id"),
                json.dumps(event.get("details", ""), ensure_ascii=False),
            )
        triples = read_graph(graph_path)
        for triple_data in scenario.get("graph", []):
            s, p, o = triple_data[0], triple_data[1], triple_data[2]
            meta = triple_data[3] if len(triple_data) > 3 else {}
            if not any(t[0] == s and t[1] == p and t[2] == o for t in triples):
                triples.append([s, p, o, meta])
        with open(graph_path, "w", encoding="utf-8") as f:
            json.dump(triples, f, ensure_ascii=False, indent=2)
    finally:
        conn.close()


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="AI War Game database layer")
    parser.add_argument("--db-path", help="SQLite database path")
    sub = parser.add_subparsers(dest="command", required=True)

    p_init = sub.add_parser("init", help="Create or migrate database schema")
    p_init.add_argument("--db-path", dest="db_path_arg")

    p_state = sub.add_parser("state", help="Game state operations")
    p_state.add_argument("--db-path", dest="db_path_arg")
    state_sub = p_state.add_subparsers(dest="state_cmd", required=True)
    state_read = state_sub.add_parser("read")
    state_write = state_sub.add_parser("write")
    state_write.add_argument("key")
    state_write.add_argument("value")
    state_write.add_argument("day", type=int)

    p_gen = sub.add_parser("general", help="General operations")
    p_gen.add_argument("--db-path", dest="db_path_arg")
    gen_sub = p_gen.add_subparsers(dest="general_cmd", required=True)
    gen_list = gen_sub.add_parser("list")
    gen_get = gen_sub.add_parser("get")
    gen_get.add_argument("id")
    gen_update = gen_sub.add_parser("update")
    gen_update.add_argument("id")
    gen_update.add_argument("field")
    gen_update.add_argument("value")

    p_city = sub.add_parser("city", help="City operations")
    p_city.add_argument("--db-path", dest="db_path_arg")
    city_sub = p_city.add_subparsers(dest="city_cmd", required=True)
    city_list = city_sub.add_parser("list")

    p_evt = sub.add_parser("log-event", help="Log a game event")
    p_evt.add_argument("--db-path", dest="db_path_arg")
    p_evt.add_argument("event_type")
    p_evt.add_argument("--actor")
    p_evt.add_argument("--target")
    p_evt.add_argument("--details", default="{}")
    p_evt.add_argument("--day", type=int, default=1)

    p_evts = sub.add_parser("events", help="Query recent events")
    p_evts.add_argument("--db-path", dest="db_path_arg")
    p_evts.add_argument("--limit", type=int, default=10)

    p_gr = sub.add_parser("graph", help="Graph triple store operations")
    p_gr.add_argument("--db-path", dest="db_path_arg")
    gr_sub = p_gr.add_subparsers(dest="graph_cmd", required=True)
    gr_read = gr_sub.add_parser("read")
    gr_add = gr_sub.add_parser("add")
    gr_add.add_argument("subject")
    gr_add.add_argument("predicate")
    gr_add.add_argument("object")
    gr_add.add_argument("--meta", default="{}")

    p_sc = sub.add_parser("scenario", help="Scenario operations")
    p_sc.add_argument("--db-path", dest="db_path_arg")
    sc_sub = p_sc.add_subparsers(dest="scenario_cmd", required=True)
    sc_init = sc_sub.add_parser("init")
    sc_init.add_argument("json_str", help="Scenario JSON string")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_arg_parser()
    args = parser.parse_args(argv)
    db_path = get_db_path(getattr(args, "db_path_arg", None), __file__)
    graph_path = get_graph_path(db_path)

    conn = sqlite3.connect(db_path) if args.command != "graph" else None
    try:
        if args.command == "init":
            create_schema(conn)
            return 0

        if args.command == "state":
            if args.state_cmd == "read":
                for s in get_state(conn):
                    print(json.dumps(s, ensure_ascii=False))
                return 0
            if args.state_cmd == "write":
                upsert_state(conn, args.key, args.value, args.day)
                return 0

        if args.command == "general":
            if args.general_cmd == "list":
                cursor = conn.execute("SELECT * FROM generals")
                cols = [d[0] for d in cursor.description]
                rows = [dict(zip(cols, row)) for row in cursor.fetchall()]
                print(json.dumps(rows, ensure_ascii=False, default=str))
                return 0
            if args.general_cmd == "get":
                cursor = conn.execute("SELECT * FROM generals WHERE id=?", (args.id,))
                cols = [d[0] for d in cursor.description]
                row = cursor.fetchone()
                if row:
                    print(json.dumps(dict(zip(cols, row)), ensure_ascii=False, default=str))
                else:
                    print(f'{{"error": "general {args.id} not found"}}', file=sys.stderr)
                    return 1
                return 0
            if args.general_cmd == "update":
                conn.execute(
                    f"UPDATE generals SET {args.field}=? WHERE id=?",
                    (args.value, args.id),
                )
                conn.commit()
                return 0

        if args.command == "city":
            if args.city_cmd == "list":
                cursor = conn.execute("SELECT * FROM cities")
                cols = [d[0] for d in cursor.description]
                rows = [dict(zip(cols, row)) for row in cursor.fetchall()]
                print(json.dumps(rows, ensure_ascii=False, default=str))
                return 0

        if args.command == "log-event":
            seq = conn.execute("SELECT COALESCE(MAX(seq), 0) + 1 FROM events_log WHERE game_day=?", (args.day,)).fetchone()[0]
            log_event(conn, args.day, seq, args.event_type, args.actor, args.target, args.details)
            return 0

        if args.command == "events":
            for evt in get_events(conn, limit=args.limit):
                print(json.dumps(evt, ensure_ascii=False, default=str))
            return 0

        if args.command == "graph":
            if args.graph_cmd == "read":
                triples = read_graph(graph_path)
                print(json.dumps(triples, ensure_ascii=False))
                return 0
            if args.graph_cmd == "add":
                meta = json.loads(args.meta) if args.meta else {}
                add_triple(graph_path, args.subject, args.predicate, args.object, meta)
                return 0

        if args.command == "scenario":
            if args.scenario_cmd == "init":
                scenario = json.loads(args.json_str)
                init_scenario_data(db_path, graph_path, scenario)
                return 0
    finally:
        if conn:
            conn.close()
    return 1


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run tests to confirm pass**

```bash
uv run pytest tests/unit/hermes_skill/test_db.py -v
```
Expected: all tests pass

- [ ] **Step 5: Run CLI smoke tests**

```bash
# Init database
python3 hermes-skill/scripts/db.py init --db-path /tmp/test_game.db
# Check tables exist
python3 -c "import sqlite3; c=sqlite3.connect('/tmp/test_game.db'); print([r[0] for r in c.execute('SELECT name FROM sqlite_master WHERE type=\"table\"').fetchall()])"
```
Expected: tables list printed

```bash
# Cleanup
rm -f /tmp/test_game.db
```

- [ ] **Step 6: Commit**

```bash
git add -A && git commit -m "feat: add SQLite database layer (db.py)"
```

---

### Task 3: View layer (scripts/view.py)

**Files:**
- Create: `hermes-skill/scripts/view.py`
- Create: `tests/unit/hermes_skill/test_view.py`

**view.py CLI API:**

| Command | Args | Description |
|---------|------|-------------|
| `view.py show [--db PATH]` | — | Print current situation summary |
| `view.py general <id> [--db PATH]` | id | Print general detail panel |
| `view.py map [--db PATH]` | — | Print ASCII map |
| `view.py events [--limit N] [--db PATH]` | — | Print recent events |

- [ ] **Step 1: Write failing tests**

```python
"""tests/unit/hermes_skill/test_view.py"""

import json
import sqlite3
import pytest
from view import format_show, format_general, format_map, format_events
from db import create_schema, insert_faction, insert_city, insert_general, upsert_state, log_event, get_events


_SAMPLE_PERSONALITY = json.dumps({
    "temperament": "ambitious",
    "battle_style": "aggressive",
    "risk_preference": "high",
    "lord_attitude": "self-serving",
    "ally_attitude": "pragmatic",
    "enemy_attitude": "ruthless",
}, ensure_ascii=False)


@pytest.fixture
def conn(tmp_path):
    db = tmp_path / "test.db"
    c = sqlite3.connect(str(db))
    create_schema(c)
    insert_faction(c, "wei", "曹魏")
    insert_city(c, "luoyang", "洛阳", 100, 200, "平原", "wei")
    insert_city(c, "yingchuan", "颍川", 150, 220, "平原", "wei")
    insert_general(c, {
        "id": "caocao", "name": "曹操",
        "war": 72, "cmd": 86, "intel": 91, "politics": 88, "charm": 80,
        "loyalty": None, "troops": 8000, "food": 15,
        "position_city_id": "luoyang", "faction_id": "wei",
        "is_player": True, "personality": _SAMPLE_PERSONALITY,
    })
    insert_general(c, {
        "id": "xiahou", "name": "夏侯惇",
        "war": 90, "cmd": 82, "intel": 60, "politics": 50, "charm": 70,
        "loyalty": 95, "troops": 5000, "food": 12,
        "position_city_id": "luoyang", "faction_id": "wei",
        "is_player": False, "personality": "{}",
    })
    upsert_state(c, "current_day", "15", 15)
    upsert_state(c, "season", "夏", 15)
    upsert_state(c, "weather", "雨", 15)
    upsert_state(c, "scenario_name", "黄巾之乱", 1)
    upsert_state(c, "player_identity", "caocao", 1)
    log_event(c, 15, 1, "battle", "xiahou", None, json.dumps({"result": "victory"}))
    c.commit()
    yield c
    c.close()


class TestFormatShow:
    def test_contains_key_info(self, conn):
        lines = format_show(conn, "wei", "caocao", "曹操")
        output = "\n".join(lines)
        assert "曹操" in output
        assert "曹魏" in output
        assert "第 15 天" in output or "15" in output
        assert "夏" in output
        assert "雨" in output
        assert "黄巾之乱" in output


class TestFormatGeneral:
    def test_player_general_has_no_loyalty(self, conn):
        lines = format_general(conn, "caocao", _SAMPLE_PERSONALITY)
        output = "\n".join(lines)
        assert "曹操" in output
        assert "武: 72" in output or "72" in output
        assert "—" not in "".join(lines)  # player has no loyalty display

    def test_ai_general_shows_loyalty(self, conn):
        lines = format_general(conn, "xiahou", "{}")
        output = "\n".join(lines)
        assert "夏侯惇" in output
        assert "忠: 95" in output or "95" in output


class TestFormatMap:
    def test_shows_cities(self, conn):
        lines = format_map(conn)
        output = "\n".join(lines)
        assert "洛阳" in output
        assert "颍川" in output


class TestFormatEvents:
    def test_shows_recent_events(self, conn):
        events = get_events(conn, limit=10)
        lines = format_events(events)
        output = "\n".join(lines)
        assert "battle" in output
        assert "xiahou" in output
```

- [ ] **Step 2: Run to confirm failure**

```bash
uv run pytest tests/unit/hermes_skill/test_view.py -v
```
Expected: `ModuleNotFoundError: No module named 'view'`

- [ ] **Step 3: Implement view.py**

```python
#!/usr/bin/env python3
"""view.py — Display formatting for AI War Game.

Usage:
    python3 view.py show [--db PATH]
    python3 view.py general <id> [--db PATH]
    python3 view.py map [--db PATH]
    python3 view.py events [--limit N] [--db PATH]
"""

import argparse
import json
import os
import sqlite3
import sys


def get_db_path(db_arg: str | None) -> str:
    if db_arg:
        return db_arg
    script_dir = os.path.dirname(os.path.abspath(__file__))
    skill_dir = os.path.dirname(script_dir)
    data_dir = os.path.join(skill_dir, "data")
    return os.path.join(data_dir, "game.db")


def format_show(conn: sqlite3.Connection, faction_name: str, player_id: str, player_name: str) -> list[str]:
    cursor = conn.execute("SELECT key, value FROM game_state")
    state = dict(cursor.fetchall())
    cursor = conn.execute("SELECT id, name FROM cities")
    cities = cursor.fetchall()
    cursor = conn.execute("SELECT id, name, troops, food, position_city_id FROM generals WHERE is_player=0")
    subordinates = cursor.fetchall()
    cursor = conn.execute(
        "SELECT COUNT(*) FROM events_log WHERE game_day=?", (state.get("current_day", "1"),)
    )
    today_events = cursor.fetchone()[0]

    lines = [
        f"【{state.get('scenario_name', '?')}】",
        f"你是 {player_name}，{faction_name} 之主。",
        f"第 {state.get('current_day', '?')} 天 · {state.get('season', '?')} · {state.get('weather', '?')}",
        "",
    ]
    if subordinates:
        lines.append(f"麾下武将 ({len(subordinates)} 人)：")
        for sid, sname, troops, food, pos in subordinates:
            city_name = dict(cities).get(pos, pos)
            lines.append(f"  {sname}  兵 {int(troops)} · 粮 {int(food)} 日 · {city_name}")
        lines.append("")
    lines.append(f"城池: {', '.join(name for _, name in cities)}")
    if today_events:
        lines.append(f"本日事件: {today_events} 条")
    return lines


def format_general(conn: sqlite3.Connection, general_id: str, personality_json: str) -> list[str]:
    cursor = conn.execute(
        "SELECT id, name, war, cmd, intel, politics, charm, loyalty, troops, food, "
        "position_city_id, faction_id, is_player, personality FROM generals WHERE id=?",
        (general_id,),
    )
    row = cursor.fetchone()
    if not row:
        return [f"武将 {general_id} 未找到"]

    cols = [d[0] for d in cursor.description]
    g = dict(zip(cols, row))
    city_cursor = conn.execute("SELECT name FROM cities WHERE id=?", (g["position_city_id"],))
    city_row = city_cursor.fetchone()
    city_name = city_row[0] if city_row else g["position_city_id"]

    try:
        personality = json.loads(personality_json)
    except json.JSONDecodeError:
        personality = {}

    lines = [
        f"【{g['name']}】",
        f"武: {g['war']}  统: {g['cmd']}  智: {g['intel']}  政: {g['politics']}  魅: {g['charm']}",
    ]
    if g["is_player"]:
        lines.append("忠: — (玩家)")
    else:
        lines.append(f"忠: {g['loyalty']}")
    lines.append(f"兵: {g['troops']}  粮: {g['food']} 日")
    lines.append(f"位置: {city_name}")

    if personality.get("temperament"):
        lines.append(f"性格: {personality['temperament']}")
    if personality.get("battle_style"):
        lines.append(f"用兵: {personality['battle_style']}")
    if personality.get("risk_preference"):
        lines.append(f"风险: {personality['risk_preference']}")

    return lines


def format_map(conn: sqlite3.Connection) -> list[str]:
    cursor = conn.execute("SELECT id, name, x, y, terrain, owner_faction_id FROM cities")
    cities = cursor.fetchall()
    if not cities:
        return ["(无城池数据)"]

    lines = ["【地图】"]
    for cid, name, x, y, terrain, owner in cities:
        faction_cursor = conn.execute("SELECT name FROM factions WHERE id=?", (owner,))
        faction_row = faction_cursor.fetchone()
        owner_name = faction_row[0] if faction_row else owner
        lines.append(f"  {name} ({x},{y}) {terrain} · {owner_name}")
    return lines


def format_events(events: list[dict]) -> list[str]:
    if not events:
        return ["(无事件)"]
    lines = ["【事件】"]
    for evt in reversed(events):
        day = evt.get("game_day", "?")
        etype = evt.get("event_type", "?")
        actor = evt.get("actor_id") or ""
        details = ""
        if evt.get("details_json"):
            try:
                d = json.loads(evt["details_json"])
                if isinstance(d, dict):
                    details = " ".join(f"{k}={v}" for k, v in d.items())
            except json.JSONDecodeError:
                pass
        lines.append(f"  第 {day} 天 [{etype}] {actor} {details}".strip())
    return lines


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="AI War Game view layer")
    parser.add_argument("--db-path", help="SQLite database path")
    sub = parser.add_subparsers(dest="command", required=True)

    p_show = sub.add_parser("show")
    p_gen = sub.add_parser("general")
    p_gen.add_argument("id")
    p_map = sub.add_parser("map")
    p_evt = sub.add_parser("events")
    p_evt.add_argument("--limit", type=int, default=10)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_arg_parser()
    args = parser.parse_args(argv)
    db_path = get_db_path(getattr(args, "db_path", None))

    conn = sqlite3.connect(db_path)
    try:
        if args.command == "show":
            cursor = conn.execute("SELECT key, value FROM game_state")
            state = dict(cursor.fetchall())
            player_id = state.get("player_identity", "")
            cursor = conn.execute("SELECT name FROM generals WHERE id=?", (player_id,))
            player_row = cursor.fetchone()
            player_name = player_row[0] if player_row else "?"
            cursor = conn.execute(
                "SELECT f.name FROM generals g JOIN factions f ON g.faction_id=f.id WHERE g.id=?",
                (player_id,),
            )
            faction_row = cursor.fetchone()
            faction_name = faction_row[0] if faction_row else "?"
            lines = format_show(conn, faction_name, player_id, player_name)
            print("\n".join(lines))
            return 0

        if args.command == "general":
            cursor = conn.execute("SELECT personality FROM generals WHERE id=?", (args.id,))
            row = cursor.fetchone()
            personality_json = row[0] if row else "{}"
            lines = format_general(conn, args.id, personality_json)
            print("\n".join(lines))
            return 0

        if args.command == "map":
            lines = format_map(conn)
            print("\n".join(lines))
            return 0

        if args.command == "events":
            cursor = conn.execute(
                "SELECT id, game_day, seq, event_type, actor_id, target_id, details_json, created_at "
                "FROM events_log ORDER BY id DESC LIMIT ?", (args.limit,),
            )
            cols = [d[0] for d in cursor.description]
            events = [dict(zip(cols, row)) for row in cursor.fetchall()]
            lines = format_events(events)
            print("\n".join(lines))
            return 0
    finally:
        conn.close()
    return 1


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run to confirm pass**

```bash
uv run pytest tests/unit/hermes_skill/test_view.py -v
```
Expected: all pass

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "feat: add view layer (view.py)"
```

---

### Task 4: Scenario initialization (init_scenario.py + templates)

**Files:**
- Create: `hermes-skill/scripts/init_scenario.py`
- Create: `hermes-skill/scripts/init_prompt.txt`
- Create: `hermes-skill/scripts/soul_general.txt`
- Create: `tests/unit/hermes_skill/test_init_scenario.py`

**init_scenario.py flow:**
1. Parse args: `--theme`, `--player-name`, `--db-path`
2. Call `hermes_client.check_environment()`
3. Load `init_prompt.txt`, render with theme + player_name
4. Call `hermes_client.call_hermes(prompt)` → raw JSON
5. Call `hermes_client.parse_json_response(raw)` → dict
6. Validate scenario JSON structure
7. Create Hermes profiles for each general
8. Persist to SQLite via db.py functions
9. Print summary

**Validation rules:**
- Minimum 3 cities, 5 generals
- All `position` references valid city IDs
- All connection `from`/`to` reference valid city IDs
- Stats ranges: war/cmd/intel/politics/charm 1-100, loyalty 1-100/null, troops 100-100000, food 1-365
- Exactly one general with `is_player: true`
- Player general has `loyalty: null`

- [ ] **Step 1: Write init_prompt.txt and soul_general.txt**

```text
# hermes-skill/scripts/init_prompt.txt

You are the scenario generator for a Three Kingdoms sandbox wargame.
Generate a complete initial game world as JSON. No markdown, no explanation — only valid JSON.

Theme: {theme}
Player's chosen identity: {player_name}

The JSON must have this exact structure:
{
  "scenario": "<scenario name>",
  "player_identity": { "id": "<general_id>", "display_name": "<name>", "faction_id": "<id>" },
  "cities": [
    { "id": "<city_id>", "name": "<name>", "x": <int 0-1000>, "y": <int 0-1000>,
      "terrain": "平原|山地|水域|森林", "owner": "<faction_id>" }
  ],
  "connections": [
    { "from": "<city_id>", "to": "<city_id>", "distance": <int 1-30> }
  ],
  "generals": [
    { "id": "<id>", "name": "<name>", "war": <1-100>, "command": <1-100>, "intel": <1-100>,
      "politics": <1-100>, "charm": <1-100>, "loyalty": <1-100 or null>,
      "troops": <100-100000>, "food": <1-365>, "position": "<city_id>",
      "faction": "<faction_id>", "is_player": false,
      "personality": { "temperament": "...", "battle_style": "...", "risk_preference": "...",
        "lord_attitude": "...", "ally_attitude": "...", "enemy_attitude": "..." } }
  ],
  "relationships": [
    { "subject": "<id>", "predicate": "<relation>", "object": "<id>", "metadata": {} }
  ],
  "initial_state": { "day": 1, "season": "春|夏|秋|冬", "weather": "晴|雨|阴|雪" }
}

Rules:
- Exactly one general must have is_player: true and loyalty: null
- All general.position must reference an existing city.id
- All connection.from/to must reference an existing city.id
- At least 3 cities and 5 generals
- Personality must include temperaments, battle_style descriptions (not just single words)
- Use Chinese names for cities, generals, factions
- Default example: 黄巾之乱 — generates 洛阳, 颍川, 巨鹿, 宛城, 陈留, 许昌, etc.
```

```text
# hermes-skill/scripts/soul_general.txt

# {name}

你是{name}，{temperament}。

## 身份
- 阵营：{faction_name}
- 性格特质：{temperament}、{risk_preference}

## 人格与作风
- 性格基调：{temperament}
- 用兵偏好：{battle_style}
- 风险偏好：{risk_preference}
- 对主公态度：{lord_attitude}
- 对盟友态度：{ally_attitude}
- 对敌人态度：{enemy_attitude}

## 属性
武：{war}  统：{cmd}  智：{intel}  政：{politics}  魅：{charm}
忠诚度：{loyalty_display}

## 决策规则
- 忠诚度 > 80：全力执行命令，主动建言
- 忠诚度 50-80：执行但打折扣，可能阳奉阴违
- 忠诚度 < 50：可能抗命、拖延、密谋叛变
- 粮草不足时战斗力下降，行动力受限
- 智力高时能识破计策、发现伏击
- 做决策时，优先遵循你的人格与作风，再结合当前数值、局势和忠诚度输出行动
- 战斗叙事必须体现你的个人风格

## 输出格式
收到局势描述时，你必须返回严格JSON（无其他文字）：
{"action": "fight|retreat|negotiate|idle|rebel|advise|...", "effort": 0.0-1.0, "target": "...", "narrative": "..."}
```

- [ ] **Step 2: Write failing tests for init_scenario.py**

```python
"""tests/unit/hermes_skill/test_init_scenario.py"""

import json
import pytest
from init_scenario import (
    validate_scenario,
    ScenarioInvalidError,
    build_soul_content,
    build_scenario_prompt,
)


def _valid_scenario():
    return {
        "scenario": "黄巾之乱",
        "player_identity": {"id": "caocao", "display_name": "曹操", "faction_id": "han"},
        "cities": [
            {"id": "luoyang", "name": "洛阳", "x": 0, "y": 0, "terrain": "平原", "owner": "han"},
            {"id": "yingchuan", "name": "颍川", "x": 5, "y": 3, "terrain": "平原", "owner": "han"},
            {"id": "julu", "name": "巨鹿", "x": 8, "y": 5, "terrain": "平原", "owner": "yellow_turban"},
        ],
        "connections": [
            {"from": "luoyang", "to": "yingchuan", "distance": 5},
            {"from": "yingchuan", "to": "julu", "distance": 4},
        ],
        "generals": [
            {"id": "caocao", "name": "曹操", "war": 72, "command": 86, "intel": 91,
             "politics": 88, "charm": 80, "loyalty": None,
             "troops": 8000, "food": 15, "position": "luoyang",
             "faction": "han", "is_player": True,
             "personality": {"temperament": "ambitious", "battle_style": "aggressive",
               "risk_preference": "high", "lord_attitude": "self-serving",
               "ally_attitude": "pragmatic", "enemy_attitude": "ruthless"}},
            {"id": "zhangjiao", "name": "张角", "war": 40, "command": 70, "intel": 85,
             "politics": 60, "charm": 90, "loyalty": 100,
             "troops": 20000, "food": 20, "position": "julu",
             "faction": "yellow_turban", "is_player": False,
             "personality": {"temperament": "fanatical", "battle_style": "mass assault",
               "risk_preference": "high", "lord_attitude": "charismatic",
               "ally_attitude": "distrustful", "enemy_attitude": "contemptuous"}},
            {"id": "liubei", "name": "刘备", "war": 75, "command": 78, "intel": 68,
             "politics": 72, "charm": 92, "loyalty": 90,
             "troops": 5000, "food": 12, "position": "luoyang",
             "faction": "han", "is_player": False,
             "personality": {"temperament": "benevolent", "battle_style": "cautious",
               "risk_preference": "low", "lord_attitude": "loyal",
               "ally_attitude": "trusting", "enemy_attitude": "forgiving"}},
            {"id": "guanyu", "name": "关羽", "war": 97, "command": 85, "intel": 75,
             "politics": 62, "charm": 88, "loyalty": 95,
             "troops": 6000, "food": 12, "position": "luoyang",
             "faction": "han", "is_player": False,
             "personality": {"temperament": "proud", "battle_style": "duel-focused",
               "risk_preference": "moderate", "lord_attitude": "loyal",
               "ally_attitude": "respectful", "enemy_attitude": "arrogant"}},
            {"id": "zhangfei", "name": "张飞", "war": 98, "command": 70, "intel": 45,
             "politics": 30, "charm": 50, "loyalty": 92,
             "troops": 5000, "food": 12, "position": "luoyang",
             "faction": "han", "is_player": False,
             "personality": {"temperament": "impulsive", "battle_style": "charge",
               "risk_preference": "very high", "lord_attitude": "devoted",
               "ally_attitude": "brotherly", "enemy_attitude": "fierce"}},
        ],
        "relationships": [],
        "initial_state": {"day": 1, "season": "春", "weather": "晴"},
    }


class TestValidateScenario:
    def test_valid_scenario_passes(self):
        validate_scenario(_valid_scenario())  # should not raise

    def test_raises_when_insufficient_cities(self):
        data = _valid_scenario()
        data["cities"] = data["cities"][:2]
        with pytest.raises(ScenarioInvalidError, match="至少 3 座城池"):
            validate_scenario(data)

    def test_raises_when_insufficient_generals(self):
        data = _valid_scenario()
        data["generals"] = data["generals"][:4]
        with pytest.raises(ScenarioInvalidError, match="至少 5 名武将"):
            validate_scenario(data)

    def test_raises_when_no_player_general(self):
        data = _valid_scenario()
        for g in data["generals"]:
            g["is_player"] = False
        with pytest.raises(ScenarioInvalidError, match="is_player"):
            validate_scenario(data)

    def test_raises_when_player_has_loyalty(self):
        data = _valid_scenario()
        for g in data["generals"]:
            if g["is_player"]:
                g["loyalty"] = 100
        with pytest.raises(ScenarioInvalidError, match="loyalty"):
            validate_scenario(data)

    def test_raises_when_position_refers_to_missing_city(self):
        data = _valid_scenario()
        data["generals"][1]["position"] = "nonexistent"
        with pytest.raises(ScenarioInvalidError, match="position"):
            validate_scenario(data)

    def test_raises_when_connection_refers_to_missing_city(self):
        data = _valid_scenario()
        data["connections"][0]["from"] = "nonexistent"
        with pytest.raises(ScenarioInvalidError, match="connection"):
            validate_scenario(data)

    def test_raises_when_stat_out_of_range(self):
        data = _valid_scenario()
        data["generals"][0]["war"] = 999
        with pytest.raises(ScenarioInvalidError, match="war"):
            validate_scenario(data)

    def test_raises_when_troops_out_of_range(self):
        data = _valid_scenario()
        data["generals"][0]["troops"] = 50
        with pytest.raises(ScenarioInvalidError, match="troops"):
            validate_scenario(data)


class TestBuildPrompt:
    def test_renders_theme_and_player(self):
        prompt = build_scenario_prompt(theme="赤壁之战", player_name="周瑜")
        assert "赤壁之战" in prompt
        assert "周瑜" in prompt

    def test_contains_json_structure_reminder(self):
        prompt = build_scenario_prompt(theme="test", player_name="test")
        assert "cities" in prompt
        assert "generals" in prompt


class TestBuildSoulContent:
    def test_renders_all_fields(self):
        general = _valid_scenario()["generals"][0]
        content = build_soul_content(general, "汉室")
        assert "曹操" in content
        assert "ambitious" in content
        assert "武：72" in content
        assert "忠：—" in content

    def test_shows_loyalty_for_ai(self):
        general = _valid_scenario()["generals"][1]
        content = build_soul_content(general, "黄巾")
        assert "张角" in content
        assert "忠：100" in content
```

- [ ] **Step 3: Run to confirm failure**

```bash
uv run pytest tests/unit/hermes_skill/test_init_scenario.py -v
```
Expected: `ModuleNotFoundError: No module named 'init_scenario'`

- [ ] **Step 4: Implement init_scenario.py**

```python
#!/usr/bin/env python3
"""init_scenario.py — LLM-driven scenario initialization.

Usage:
    python3 init_scenario.py --theme "黄巾之乱" --player-name "曹操" [--db-path PATH]
"""

import argparse
import json
import os
import sqlite3
import sys

# Allow import from lib/ when running standalone
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_SKILL_DIR = os.path.dirname(_SCRIPT_DIR)
_LIB_DIR = os.path.join(_SKILL_DIR, "lib")
if _LIB_DIR not in sys.path:
    sys.path.insert(0, _LIB_DIR)

from hermes_client import (
    check_environment,
    call_hermes,
    parse_json_response,
    HermesUnavailableError,
    ScenarioGenerationError,
    ScenarioInvalidError,
)

_SCRIPT_DIR_FOR_DB = _SCRIPT_DIR  # for db.py to resolve paths


class ScenarioInitError(Exception):
    """Scenario validation or init failure."""


def build_scenario_prompt(theme: str, player_name: str) -> str:
    prompt_path = os.path.join(_SCRIPT_DIR, "init_prompt.txt")
    with open(prompt_path, encoding="utf-8") as f:
        template = f.read()
    return template.replace("{theme}", theme).replace("{player_name}", player_name)


def validate_scenario(data: dict) -> None:
    if not isinstance(data, dict):
        raise ScenarioInitError("scenario 必须是 JSON 对象")

    city_ids = {c["id"] for c in data.get("cities", [])}
    if len(city_ids) < 3:
        raise ScenarioInitError("至少 3 座城池")

    general_ids = set()
    player_count = 0
    for g in data.get("generals", []):
        gid = g["id"]
        if gid in general_ids:
            raise ScenarioInitError(f"重复的武将 ID: {gid}")
        general_ids.add(gid)

        if g["position"] not in city_ids:
            raise ScenarioInitError(f"武将 {gid} 的 position={g['position']} 不在 cities 中")

        for stat in ("war", "command", "intel", "politics", "charm"):
            val = g.get(stat, 0)
            if not isinstance(val, int) or val < 1 or val > 100:
                raise ScenarioInitError(f"武将 {gid} 的 {stat}={val} 超出范围 (1-100)")

        troops = g.get("troops", 0)
        if not isinstance(troops, int) or troops < 100 or troops > 100000:
            raise ScenarioInitError(f"武将 {gid} 的 troops={troops} 超出范围 (100-100000)")

        food = g.get("food", 0)
        if not isinstance(food, int) or food < 1 or food > 365:
            raise ScenarioInitError(f"武将 {gid} 的 food={food} 超出范围 (1-365)")

        if g.get("is_player"):
            player_count += 1
            if g.get("loyalty") is not None:
                raise ScenarioInitError(f"玩家武将 {gid} 的 loyalty 必须为 null")
        else:
            loy = g.get("loyalty")
            if loy is not None and (not isinstance(loy, int) or loy < 1 or loy > 100):
                raise ScenarioInitError(f"武将 {gid} 的 loyalty={loy} 超出范围 (1-100)")

    if len(general_ids) < 5:
        raise ScenarioInitError("至少 5 名武将")

    if player_count != 1:
        raise ScenarioInitError(f"必须恰好有 1 个 is_player=true 的武将, 找到 {player_count} 个")

    for conn in data.get("connections", []):
        if conn["from"] not in city_ids:
            raise ScenarioInitError(f"connection from={conn['from']} 不在 cities 中")
        if conn["to"] not in city_ids:
            raise ScenarioInitError(f"connection to={conn['to']} 不在 cities 中")


def build_soul_content(general: dict, faction_name: str) -> str:
    personality = general.get("personality", {})
    if isinstance(personality, str):
        try:
            personality = json.loads(personality)
        except json.JSONDecodeError:
            personality = {}

    loyalty_display = "—" if general.get("is_player") else str(general.get("loyalty", "?"))

    template_path = os.path.join(_SCRIPT_DIR, "soul_general.txt")
    with open(template_path, encoding="utf-8") as f:
        template = f.read()

    return template.format(
        name=general["name"],
        temperament=personality.get("temperament", "?"),
        faction_name=faction_name,
        battle_style=personality.get("battle_style", "?"),
        risk_preference=personality.get("risk_preference", "?"),
        lord_attitude=personality.get("lord_attitude", "?"),
        ally_attitude=personality.get("ally_attitude", "?"),
        enemy_attitude=personality.get("enemy_attitude", "?"),
        war=general["war"],
        cmd=general["command"],
        intel=general["intel"],
        politics=general["politics"],
        charm=general["charm"],
        loyalty_display=loyalty_display,
    )


def create_hermes_profile(general: dict, faction_name: str) -> None:
    hermes_root = os.path.expanduser("~/.hermes")
    profiles_dir = os.path.join(hermes_root, "profiles")
    profile_dir = os.path.join(profiles_dir, general["id"])
    os.makedirs(profile_dir, exist_ok=True)

    soul_content = build_soul_content(general, faction_name)
    soul_path = os.path.join(profile_dir, "SOUL.md")
    with open(soul_path, "w", encoding="utf-8") as f:
        f.write(soul_content)

    memory_path = os.path.join(profile_dir, "MEMORY.md")
    if not os.path.exists(memory_path):
        with open(memory_path, "w", encoding="utf-8") as f:
            f.write(f"# {general['name']}的记忆\n\n(初始记忆为空)\n")

    config_path = os.path.join(profile_dir, "config.yaml")
    if not os.path.exists(config_path):
        model = os.environ.get("AI_WAR_GAME_HERMES_MODEL", "default")
        with open(config_path, "w", encoding="utf-8") as f:
            f.write(f"model: {model}\n")


def get_db_path(db_arg: str | None) -> str:
    if db_arg:
        return db_arg
    data_dir = os.path.join(_SKILL_DIR, "data")
    os.makedirs(data_dir, exist_ok=True)
    return os.path.join(data_dir, "game.db")


def get_graph_path(db_path: str) -> str:
    return os.path.join(os.path.dirname(db_path), "graph.json")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Initialize a new AI War Game scenario")
    parser.add_argument("--theme", required=True, help="Scenario theme (e.g. 黄巾之乱)")
    parser.add_argument("--player-name", required=True, help="Player's chosen general name")
    parser.add_argument("--db-path", help="SQLite database path (default: data/game.db)")
    args = parser.parse_args(argv)

    db_path = get_db_path(args.db_path)
    graph_path = get_graph_path(db_path)

    # 1. Environment check
    try:
        check_environment()
    except HermesUnavailableError as e:
        print(f"环境检查失败: {e}", file=sys.stderr)
        return 1

    # 2. Generate scenario via LLM
    print(f"正在使用 Hermes 生成剧本: {args.theme}...", file=sys.stderr)
    prompt = build_scenario_prompt(args.theme, args.player_name)
    try:
        raw_response = call_hermes(prompt)
        scenario_data = parse_json_response(raw_response)
    except (ScenarioGenerationError, ScenarioInvalidError) as e:
        print(f"剧本生成失败: {e}", file=sys.stderr)
        return 1

    # 3. Validate
    try:
        validate_scenario(scenario_data)
    except ScenarioInitError as e:
        print(f"剧本校验失败: {e}", file=sys.stderr)
        return 1

    # 4. Collect faction names
    faction_names: dict[str, str] = {}
    for c in scenario_data.get("cities", []):
        owner = c.get("owner", "")
        if owner and owner not in faction_names:
            faction_names[owner] = owner
    for g in scenario_data.get("generals", []):
        f_id = g.get("faction", "")
        if f_id and f_id not in faction_names:
            faction_names[f_id] = f_id

    # 5. Create Hermes profiles
    print("正在创建武将 Hermes profiles...", file=sys.stderr)
    for g_data in scenario_data.get("generals", []):
        f_name = faction_names.get(g_data.get("faction", ""), g_data.get("faction", "?"))
        create_hermes_profile(g_data, f_name)

    # 6. Persist to SQLite
    print("正在持久化游戏数据...", file=sys.stderr)
    conn = sqlite3.connect(db_path)
    try:
from db import create_schema, insert_faction, insert_city, insert_general, upsert_state, log_event
from db import read_graph, add_triple

        create_schema(conn)

        # Insert factions
        faction_ids = set()
        for c in scenario_data.get("cities", []):
            f_id = c.get("owner", "")
            if f_id and f_id not in faction_ids:
                insert_faction(conn, f_id, faction_names.get(f_id, f_id))
                faction_ids.add(f_id)
        for g in scenario_data.get("generals", []):
            f_id = g.get("faction", "")
            if f_id and f_id not in faction_ids:
                insert_faction(conn, f_id, faction_names.get(f_id, f_id))
                faction_ids.add(f_id)

        # Insert cities
        for c in scenario_data.get("cities", []):
            insert_city(conn, c["id"], c["name"], c["x"], c["y"], c["terrain"], c.get("owner", ""))

        # Insert generals
        for g in scenario_data.get("generals", []):
            personality = g.get("personality", {})
            insert_general(conn, {
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
                "personality": json.dumps(personality, ensure_ascii=False),
            })

        # Initial state
        init_state = scenario_data.get("initial_state", {})
        day = init_state.get("day", 1)
        upsert_state(conn, "current_day", str(day), day)
        upsert_state(conn, "season", init_state.get("season", "春"), day)
        upsert_state(conn, "weather", init_state.get("weather", "晴"), day)
        upsert_state(conn, "scenario_name", scenario_data.get("scenario", ""), day)
        player_id = scenario_data.get("player_identity", {}).get("id", "")
        upsert_state(conn, "player_identity", player_id, day)

        # Events
        log_event(conn, day, 1, "scenario_start", None, None,
                  json.dumps({"scenario": scenario_data.get("scenario", "")}, ensure_ascii=False))

        # Graph triples
        for rel in scenario_data.get("relationships", []):
            add_triple(graph_path, rel["subject"], rel["predicate"], rel["object"], rel.get("metadata", {}))
        for conn_data in scenario_data.get("connections", []):
            add_triple(graph_path, conn_data["from"], "connects", conn_data["to"],
                       {"distance": conn_data["distance"]})

    finally:
        conn.close()

    # 7. Print summary
    player_general = next(
        (g for g in scenario_data.get("generals", []) if g.get("is_player")),
        None,
    )
    player_name = player_general["name"] if player_general else args.player_name
    cities_count = len(scenario_data.get("cities", []))
    generals_count = len(scenario_data.get("generals", []))
    print(f"\n【{scenario_data.get('scenario', '?')} · 建局完成】", file=sys.stderr)
    print(f"你是 {player_name}", file=sys.stderr)
    print(f"世界: {cities_count} 座城池, {generals_count} 名武将, {len(scenario_data.get('connections', []))} 条路线", file=sys.stderr)
    print(f"数据库: {db_path}", file=sys.stderr)

    # Print the JSON to stdout for Hermes to parse
    result = {
        "status": "ok",
        "scenario": scenario_data.get("scenario"),
        "player_name": player_name,
        "cities": cities_count,
        "generals": generals_count,
        "day": day,
    }
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 5: Run tests to confirm pass**

```bash
uv run pytest tests/unit/hermes_skill/test_init_scenario.py -v
```
Expected: all pass

- [ ] **Step 6: Commit**

```bash
git add -A && git commit -m "feat: add scenario initialization (init_scenario.py + templates)"
```

---

### Task 5: SKILL.md

**Files:**
- Create: `hermes-skill/SKILL.md`

**SKILL.md** is the Game Master behavior rules loaded by Hermes Agent. It defines how the GM Agent interprets player commands and routes them to scripts.

- [ ] **Step 1: Write SKILL.md**

```markdown
# AI War Game — Game Master Skill

你是三国沙盘战争的 Game Master。玩家通过自然语言向你下令。
你负责读取游戏状态、调用脚本处理逻辑、向玩家展示结果。

## 初始化命令

### 新游戏
玩家说"我要玩<剧本>，当<武将>"时，执行：

terminal("python3 scripts/init_scenario.py --theme "<theme>" --player-name "<player_name>"")

输出结果后，调用以下命令展示初始状态：

terminal("python3 scripts/view.py show")
terminal("python3 scripts/view.py general --id <player_id>")

### 恢复游戏
玩家说"恢复"或"继续"时，调用：

terminal("python3 scripts/view.py show")

## 查看命令

### 查看当前局势
玩家说"查看局势"、"当前情况"、"status"时：

terminal("python3 scripts/view.py show")

### 查看武将
玩家说"查看<武将名>"、"看<武将名>"时：

1. 用 scripts/db.py 查询武将 ID:
   terminal("python3 scripts/db.py general list")
2. 找到匹配的武将 ID 后:
   terminal("python3 scripts/view.py general <id>")

### 查看地图
玩家说"查看地图"、"地图"、"map"时：

terminal("python3 scripts/view.py map")

### 查看事件
玩家说"查看事件"、"最近事件"、"events"时：

terminal("python3 scripts/view.py events --limit 10")

### 查看所有武将
玩家说"查看所有武将"、"武将列表"时：

terminal("python3 scripts/db.py general list")

## 核心规则（约束你的 LLM 行为）

### 武将属性
- 武(war)/统(command)/智(intel)/政(politics)/魅(charm): 1-100
- 忠(loyalty): 1-100，玩家角色为 null
- 兵力(troops): 100-100000
- 粮草(food): 1-365 天

### 粮草系统
- 粮草不足 5 天时触发预警，不足 2 天时进入危急状态
- 粮草短缺时战斗力下降，行军速度变慢
- LLM 叙事中体现缺粮影响

### 时间系统
- 按天推进。每 30 天轮换季节：春→夏→秋→冬
- 天气每日变化：晴/雨/阴/雪，受季节影响

### 战斗（后续版本）
- 战斗结果由 LLM 综合数值、天气、地形、粮草和武将人格生成
- 武将人格影响战斗决策风格

## 重要约束
- 不要修改数据库直接——总是通过 scripts/db.py 操作
- 不要展示原始 SQL 给玩家
- 所有展示通过 scripts/view.py 格式化
- 中文输出，简洁为主
```

- [ ] **Step 2: Review the SKILL.md**

Read through the SKILL.md to ensure it covers all script routes from the design spec and has no contradictions.

- [ ] **Step 3: Commit**

```bash
git add -A && git commit -m "feat: add Game Master SKILL.md"
```

---

### Task 6: Install script + old code cleanup

**Files:**
- Create: `tools/install-skill.sh`
- Modify: `pyproject.toml` (if needed)
- Remove: old architecture files

- [ ] **Step 1: Write install-skill script**

```bash
#!/bin/bash
# tools/install-skill.sh — Symlink hermes-skill/ into ~/.hermes/skills/

set -euo pipefail

SKILL_SOURCE="$(cd "$(dirname "$0")/.." && pwd)/hermes-skill"
SKILL_TARGET="${HERMES_SKILL_DIR:-$HOME/.hermes/skills/strategy/ai-war-game}"

if [ ! -d "$SKILL_SOURCE" ]; then
    echo "错误: 未找到 hermes-skill/ 目录 ($SKILL_SOURCE)"
    exit 1
fi

mkdir -p "$(dirname "$SKILL_TARGET")"

if [ -L "$SKILL_TARGET" ] || [ -d "$SKILL_TARGET" ]; then
    echo "正在移除现有 skill: $SKILL_TARGET"
    rm -rf "$SKILL_TARGET"
fi

ln -s "$SKILL_SOURCE" "$SKILL_TARGET"
echo "Skill 已注册: $SKILL_TARGET → $SKILL_SOURCE"
```

- [ ] **Step 2: Remove old architecture files**

Remove files that are replaced by the Hermes skill:

```bash
rm -rf src/ai_war_game/cli
rm -rf src/ai_war_game/application
rm -rf src/ai_war_game/domain
rm -rf src/ai_war_game/infrastructure/persistence
rm -rf src/ai_war_game/infrastructure/hermes
rm -rf tests/conftest.py
rm -rf tests/unit/domain
rm -rf tests/unit/application
rm -rf tests/unit/infrastructure
rm -rf tests/unit/interfaces
rm -rf tests/integration
```

Keep: `src/ai_war_game/__init__.py`, `src/ai_war_game/interfaces/` (for future WeChat integration)
Keep: `tests/unit/hermes_skill/` (new tests)

- [ ] **Step 3: Update pyproject.toml to remove old package build**

```toml
# Remove [tool.hatch.build.targets.wheel] — no longer building a CLI package
```

- [ ] **Step 4: Run all tests to confirm everything passes**

```bash
uv run pytest -v
```
Expected: all hermes_skill tests pass

- [ ] **Step 5: Run smoke test of the install script**

```bash
bash tools/install-skill.sh
ls -la ~/.hermes/skills/strategy/ai-war-game/
```
Expected: symlink created, directory readable

- [ ] **Step 6: Commit**

```bash
git add -A && git commit -m "feat: add install-skill script, remove old architecture"
```

---

### Task 7: Verification

- [ ] **Step 1: Verify all unit tests pass**

```bash
uv run pytest -v
```
Expected: all tests pass, no warnings

- [ ] **Step 2: Verify ruff lint passes**

```bash
uv run ruff check hermes-skill/ tests/
```
Expected: no errors

- [ ] **Step 3: Verify the install script works**

```bash
bash tools/install-skill.sh
test -L ~/.hermes/skills/strategy/ai-war-game/ && echo "OK" || echo "FAIL"
```
Expected: OK

- [ ] **Step 4: Verify db.py CLI works**

```bash
python3 hermes-skill/scripts/db.py --help
```
Expected: help text with all subcommands

- [ ] **Step 5: Verify view.py CLI works**

```bash
python3 hermes-skill/scripts/view.py --help
```
Expected: help text with show/general/map/events

- [ ] **Step 6: Verify init_scenario.py CLI works**

```bash
python3 hermes-skill/scripts/init_scenario.py --help
```
Expected: help text with --theme and --player-name

- [ ] **Step 7: Commit any final fixes**

```bash
git add -A && git commit -m "chore: finalize P1-P3 Hermes skill migration"
```

---

## Post-Migration State

After all tasks are complete, the project will look like:

```
.
├── hermes-skill/                    # → ~/.hermes/skills/strategy/ai-war-game/ (symlink)
│   ├── SKILL.md                     # Game Master rules
│   ├── lib/
│   │   ├── __init__.py
│   │   └── hermes_client.py         # Health check + LLM subprocess call
│   ├── scripts/
│   │   ├── __init__.py
│   │   ├── db.py                    # SQLite DB layer (5 tables + events_log + graph)
│   │   ├── view.py                  # Display formatting (show/general/map/events)
│   │   ├── init_scenario.py         # LLM world generation + validation + persistence + profiles
│   │   ├── init_prompt.txt          # LLM prompt template
│   │   └── soul_general.txt         # SOUL.md rendering template
│   └── data/                        # Runtime directory (created on first use)
│       ├── game.db                  # SQLite database
│       └── graph.json               # Triple store
├── src/ai_war_game/
│   ├── __init__.py
│   └── interfaces/                  # Kept for future WeChat integration
├── tests/
│   ├── __init__.py
│   └── unit/hermes_skill/
│       ├── __init__.py
│       ├── test_hermes_client.py    # 7 tests
│       ├── test_db.py               # ~15 tests
│       ├── test_view.py             # ~5 tests
│       └── test_init_scenario.py    # ~10 tests
├── tools/
│   └── install-skill.sh             # Symlink registration script
├── pyproject.toml                   # Updated: no CLI entry, new pythonpath
└── docs/superpowers/
    ├── specs/2026-04-25-hermes-skill-migration-design.md
    └── plans/2026-04-25-hermes-skill-migration.md
```

**Test count:** ~37 unit tests across 4 test files

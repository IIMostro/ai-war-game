"""db.py — SQLite database layer for AI War Game."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path


def get_db_path(db_arg: str | None = None) -> str:
    if db_arg is not None:
        return db_arg
    # db.py is at src/ai_war_game/db.py → project root → data/game.db
    return str(Path(__file__).resolve().parent.parent.parent / "data" / "game.db")


def get_graph_path(db_path: str) -> str:
    db = Path(db_path)
    return str(db.with_name("graph.json"))


def create_schema(conn: sqlite3.Connection) -> None:
    conn.executescript("""
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


def insert_faction(conn: sqlite3.Connection, faction_id: str, name: str) -> None:
    conn.execute(
        "INSERT INTO factions (id, name) VALUES (?, ?)",
        (faction_id, name),
    )
    conn.commit()


def insert_city(
    conn: sqlite3.Connection,
    city_id: str,
    name: str,
    x: int,
    y: int,
    terrain: str,
    owner_faction_id: str,
) -> None:
    conn.execute(
        "INSERT INTO cities (id, name, x, y, terrain, owner_faction_id) VALUES (?, ?, ?, ?, ?, ?)",
        (city_id, name, x, y, terrain, owner_faction_id),
    )
    conn.commit()


def insert_general(conn: sqlite3.Connection, data: dict) -> None:
    conn.execute(
        """INSERT INTO generals (
            id, name, war, cmd, intel, politics, charm, loyalty,
            troops, food, position_city_id, faction_id, is_player, personality
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            data["id"],
            data["name"],
            data["war"],
            data["cmd"],
            data["intel"],
            data["politics"],
            data["charm"],
            data.get("loyalty"),
            data["troops"],
            data["food"],
            data["position_city_id"],
            data["faction_id"],
            1 if data.get("is_player") else 0,
            data["personality"],
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
    conn: sqlite3.Connection,
    game_day: int,
    seq: int,
    event_type: str,
    actor_id: str | None,
    target_id: str | None,
    details_json: str,
) -> None:
    conn.execute(
        """INSERT INTO events_log (game_day, seq, event_type, actor_id, target_id, details_json)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (game_day, seq, event_type, actor_id, target_id, details_json),
    )
    conn.commit()


def get_general(conn: sqlite3.Connection, general_id: str) -> dict | None:
    cursor = conn.execute("SELECT * FROM generals WHERE id=?", (general_id,))
    row = cursor.fetchone()
    if row is None:
        return None
    columns = [desc[0] for desc in cursor.description]
    return dict(zip(columns, row, strict=False))


def get_events(conn: sqlite3.Connection, limit: int = 10) -> list[dict]:
    cursor = conn.execute(
        """SELECT game_day, seq, event_type, actor_id, target_id, details_json
           FROM events_log ORDER BY game_day, seq LIMIT ?""",
        (limit,),
    )
    return [
        {
            "game_day": row[0],
            "seq": row[1],
            "event_type": row[2],
            "actor_id": row[3],
            "target_id": row[4],
            "details_json": row[5],
        }
        for row in cursor.fetchall()
    ]


def read_graph(graph_path: str) -> list[list]:
    with open(graph_path) as f:
        return list(json.load(f))


def add_triple(
    graph_path: str,
    subject: str,
    predicate: str,
    obj: str,
    metadata: dict | None = None,
) -> None:
    triples = read_graph(graph_path)
    triple = [subject, predicate, obj, metadata or {}]
    triples.append(triple)
    with open(graph_path, "w") as f:
        json.dump(triples, f, ensure_ascii=False)


def init_scenario_data(db_path: str, graph_path: str, scenario: dict) -> None:
    """Bulk-insert scenario data. Factions and cities must be pre-inserted before calling.

    Processes: state, generals, events, graph keys from scenario dict.
    """
    import warnings

    known_keys = {"state", "generals", "events", "graph", "scenario_name", "player_identity"}
    unexpected = set(scenario.keys()) - known_keys
    if unexpected:
        warnings.warn(f"init_scenario_data: unexpected keys ignored: {unexpected}", stacklevel=2)

    conn = sqlite3.connect(db_path)
    try:
        for key, value in scenario.get("state", {}).items():
            upsert_state(conn, key, value, 1)

        for general_data in scenario.get("generals", []):
            insert_general(conn, general_data)

        for seq, event in enumerate(scenario.get("events", []), start=1):
            log_event(
                conn,
                event.get("day", 1),
                seq,
                event.get("type", "unknown"),
                event.get("actor_id"),
                event.get("target_id"),
                json.dumps(event.get("details", event.get("details_json", {})), ensure_ascii=False),
            )

        for triple_data in scenario.get("graph", []):
            s, p, o = triple_data[0], triple_data[1], triple_data[2]
            meta = triple_data[3] if len(triple_data) > 3 else None
            add_triple(graph_path, s, p, o, meta)
    finally:
        conn.close()


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

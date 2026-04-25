"""hermes-skill/scripts/db.py — SQLite database layer for AI War Game Hermes Skill."""

import argparse
import json
import sqlite3
from pathlib import Path


def get_db_path(db_arg: str | None, script_file: str) -> str:
    if db_arg is not None:
        return db_arg
    return str(Path(script_file).resolve().parent.parent / "data" / "game.db")


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


def main() -> None:
    parser = argparse.ArgumentParser(description="AI War Game DB Manager")
    parser.add_argument("--db-path", default=None, help="Path to SQLite database file")
    sub = parser.add_subparsers(dest="command", required=True)

    init_parser = sub.add_parser("init", help="Create/migrate schema")
    init_parser.add_argument("--db-path", dest="init_db_path", default=None)

    state_parser = sub.add_parser("state", help="Game state operations")
    state_sub = state_parser.add_subparsers(dest="state_command", required=True)
    state_read = state_sub.add_parser("read", help="Print all game_state as JSON")
    state_read.add_argument("--db-path", dest="state_read_db_path", default=None)
    state_write = state_sub.add_parser("write", help="Insert or replace state entry")
    state_write.add_argument("key")
    state_write.add_argument("value")
    state_write.add_argument("day", type=int)
    state_write.add_argument("--db-path", dest="state_write_db_path", default=None)

    general_parser = sub.add_parser("general", help="General operations")
    general_sub = general_parser.add_subparsers(dest="general_command", required=True)
    general_list = general_sub.add_parser("list", help="Print generals as JSON")
    general_list.add_argument("--db-path", dest="general_list_db_path", default=None)
    general_get = general_sub.add_parser("get", help="Print single general")
    general_get.add_argument("id")
    general_get.add_argument("--db-path", dest="general_get_db_path", default=None)
    general_update = general_sub.add_parser("update", help="Update a general")
    general_update.add_argument("id")
    general_update.add_argument("field")
    general_update.add_argument("value")
    general_update.add_argument("--db-path", dest="general_update_db_path", default=None)

    city_parser = sub.add_parser("city", help="City operations")
    city_sub = city_parser.add_subparsers(dest="city_command", required=True)
    city_list = city_sub.add_parser("list", help="Print cities as JSON")
    city_list.add_argument("--db-path", dest="city_list_db_path", default=None)

    log_parser = sub.add_parser("log-event", help="Log an event")
    log_parser.add_argument("event_type")
    log_parser.add_argument("--actor", default=None)
    log_parser.add_argument("--target", default=None)
    log_parser.add_argument("--details", default="{}")
    log_parser.add_argument("--day", type=int, default=1)
    log_parser.add_argument("--db-path", dest="log_event_db_path", default=None)

    events_parser = sub.add_parser("events", help="Print events as JSON")
    events_parser.add_argument("--limit", type=int, default=10)
    events_parser.add_argument("--db-path", dest="events_db_path", default=None)

    graph_parser = sub.add_parser("graph", help="Graph triple operations")
    graph_sub = graph_parser.add_subparsers(dest="graph_command", required=True)
    graph_read = graph_sub.add_parser("read", help="Print graph triples")
    graph_read.add_argument("--db-path", dest="graph_read_db_path", default=None)
    graph_add = graph_sub.add_parser("add", help="Add triple")
    graph_add.add_argument("subject")
    graph_add.add_argument("predicate")
    graph_add.add_argument("object")
    graph_add.add_argument("--meta", default=None)
    graph_add.add_argument("--db-path", dest="graph_add_db_path", default=None)

    scenario_parser = sub.add_parser("scenario", help="Scenario operations")
    scenario_sub = scenario_parser.add_subparsers(dest="scenario_command", required=True)
    scenario_init = scenario_sub.add_parser("init", help="Bulk-insert scenario")
    scenario_init.add_argument("json_str", help="Scenario JSON string")
    scenario_init.add_argument("--db-path", dest="scenario_init_db_path", default=None)

    args = parser.parse_args()

    if args.command == "init":
        db_path = get_db_path(getattr(args, "init_db_path", None), __file__)
        conn = sqlite3.connect(db_path)
        create_schema(conn)
        conn.close()
        print(f"Schema created at {db_path}")

    elif args.command == "state":
        if args.state_command == "read":
            db_path = get_db_path(getattr(args, "state_read_db_path", None), __file__)
            conn = sqlite3.connect(db_path)
            print(json.dumps(get_state(conn), ensure_ascii=False))
            conn.close()
        elif args.state_command == "write":
            db_path = get_db_path(getattr(args, "state_write_db_path", None), __file__)
            conn = sqlite3.connect(db_path)
            upsert_state(conn, args.key, args.value, args.day)
            conn.close()

    elif args.command == "general":
        db_path = get_db_path(
            getattr(args, "general_list_db_path", None)
            or getattr(args, "general_get_db_path", None)
            or getattr(args, "general_update_db_path", None),
            __file__,
        )
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        if args.general_command == "list":
            cursor = conn.execute("SELECT * FROM generals")
            rows = [dict(row) for row in cursor.fetchall()]
            print(json.dumps(rows, ensure_ascii=False))
        elif args.general_command == "get":
            cursor = conn.execute("SELECT * FROM generals WHERE id=?", (args.id,))
            row = cursor.fetchone()
            if row:
                print(json.dumps(dict(row), ensure_ascii=False))
            else:
                print("null")
        elif args.general_command == "update":
            allowed_fields = {
                "name",
                "war",
                "cmd",
                "intel",
                "politics",
                "charm",
                "loyalty",
                "troops",
                "food",
            }
            if args.field not in allowed_fields:
                print(f"Field '{args.field}' not allowed for update")
                conn.close()
                return
            val: str | int = args.value
            if args.field in allowed_fields - {"name"}:
                val = int(args.value)
            conn.execute(f"UPDATE generals SET {args.field} = ? WHERE id = ?", (val, args.id))
            conn.commit()
            conn.close()

    elif args.command == "city":
        db_path = get_db_path(getattr(args, "city_list_db_path", None), __file__)
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        if args.city_command == "list":
            cursor = conn.execute("SELECT * FROM cities")
            rows = [dict(row) for row in cursor.fetchall()]
            print(json.dumps(rows, ensure_ascii=False))
        conn.close()

    elif args.command == "log-event":
        db_path = get_db_path(getattr(args, "log_event_db_path", None), __file__)
        conn = sqlite3.connect(db_path)
        log_event(conn, args.day, 0, args.event_type, args.actor, args.target, args.details)
        conn.close()

    elif args.command == "events":
        db_path = get_db_path(getattr(args, "events_db_path", None), __file__)
        conn = sqlite3.connect(db_path)
        print(json.dumps(get_events(conn, limit=args.limit), ensure_ascii=False))
        conn.close()

    elif args.command == "graph":
        db_path = get_db_path(
            getattr(args, "graph_read_db_path", None) or getattr(args, "graph_add_db_path", None),
            __file__,
        )
        graph_path = get_graph_path(db_path)
        if args.graph_command == "read":
            print(json.dumps(read_graph(graph_path), ensure_ascii=False))
        elif args.graph_command == "add":
            meta = json.loads(args.meta) if args.meta else None
            add_triple(graph_path, args.subject, args.predicate, args.object, meta)

    elif args.command == "scenario":
        db_path = get_db_path(getattr(args, "scenario_init_db_path", None), __file__)
        graph_path = get_graph_path(db_path)
        scenario = json.loads(args.json_str)
        init_scenario_data(db_path, graph_path, scenario)
        print(f"Scenario initialized at {db_path}")


if __name__ == "__main__":
    main()

"""autonomy.py — Check idle generals and trigger autonomous decisions.

Usage:
    python3 scripts/autonomy.py check [--db-path PATH]
    python3 scripts/autonomy.py trigger --general <id> [--db-path PATH]
    python3 scripts/autonomy.py trigger-all [--db-path PATH]
"""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_SKILL_DIR = os.path.dirname(_SCRIPT_DIR)
_LIB_DIR = os.path.join(_SKILL_DIR, "lib")
if _LIB_DIR not in sys.path:
    sys.path.insert(0, _LIB_DIR)
if _SCRIPT_DIR not in sys.path:
    sys.path.insert(0, _SCRIPT_DIR)


def get_db_path(db_arg: str | None) -> str:
    if db_arg:
        return db_arg
    data_dir = os.path.join(_SKILL_DIR, "data")
    os.makedirs(data_dir, exist_ok=True)
    return os.path.join(data_dir, "game.db")


def find_idle_generals(conn: sqlite3.Connection) -> list[dict]:
    cursor = conn.execute(
        "SELECT id, name, loyalty, troops, food, position_city_id, faction_id, personality "
        "FROM generals WHERE is_player=0"
    )
    cols = [d[0] for d in cursor.description]
    return [dict(zip(cols, row, strict=False)) for row in cursor.fetchall()]


def build_autonomy_context(general: dict, current_day: int, season: str) -> str:
    context = {
        "type": "autonomy_check",
        "current_day": current_day,
        "season": season,
        "your_status": {
            "troops": general["troops"],
            "food": general["food"],
            "loyalty": general["loyalty"],
        },
        "instruction": (
            "As a general in this world, review your situation and decide what action to take. "
            "Consider your loyalty, your troops, your food supplies, and your ambitions. "
            "Are you loyal to your lord? Are you planning something?"
        ),
    }
    return json.dumps(context, ensure_ascii=False)


def trigger_autonomy(conn: sqlite3.Connection, general_id: str) -> dict:
    from agent_comm import collect_responses, invoke_generals, send_to_inbox

    cursor = conn.execute("SELECT * FROM generals WHERE id=?", (general_id,))
    cols = [d[0] for d in cursor.description]
    row = cursor.fetchone()
    if not row:
        return {"general": general_id, "status": "error", "error": "general not found"}
    general = dict(zip(cols, row, strict=False))

    cursor = conn.execute("SELECT value FROM game_state WHERE key='current_day'")
    day_row = cursor.fetchone()
    current_day = int(day_row[0]) if day_row else 1
    cursor = conn.execute("SELECT value FROM game_state WHERE key='season'")
    season_row = cursor.fetchone()
    season = season_row[0] if season_row else "春"

    context = build_autonomy_context(general, current_day, season)
    send_to_inbox(general_id, context)
    results = invoke_generals([general_id], timeout=120)
    collected = collect_responses([general_id])

    return {
        "general": general_id,
        "name": general["name"],
        "context_sent": context,
        "invoke_result": results,
        "collected": collected,
    }


def check_and_trigger_all(conn: sqlite3.Connection) -> list[dict]:
    generals = find_idle_generals(conn)
    results = []
    for g in generals:
        result = trigger_autonomy(conn, g["id"])
        results.append(result)
    return results


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="AI War Game General Autonomy")
    sub = parser.add_subparsers(dest="command", required=True)

    p_check = sub.add_parser("check", help="List idle generals")
    p_check.add_argument("--db-path", dest="db_path_arg")

    p_trigger = sub.add_parser("trigger", help="Trigger autonomy for a general")
    p_trigger.add_argument("--general", required=True)
    p_trigger.add_argument("--db-path", dest="db_path_arg")

    p_all = sub.add_parser("trigger-all", help="Trigger autonomy for all idle generals")
    p_all.add_argument("--db-path", dest="db_path_arg")

    args = parser.parse_args(argv)
    db_path = get_db_path(getattr(args, "db_path_arg", None))

    conn = sqlite3.connect(db_path)
    try:
        if args.command == "check":
            generals = find_idle_generals(conn)
            print(json.dumps([{
                "id": g["id"],
                "name": g["name"],
                "loyalty": g["loyalty"],
                "troops": g["troops"],
                "food": g["food"],
            } for g in generals], ensure_ascii=False, default=str))
            return 0

        if args.command == "trigger":
            result = trigger_autonomy(conn, args.general)
            print(json.dumps(result, ensure_ascii=False, default=str))
            return 0

        if args.command == "trigger-all":
            results = check_and_trigger_all(conn)
            print(json.dumps(results, ensure_ascii=False, default=str))
            return 0
    finally:
        conn.close()
    return 1


if __name__ == "__main__":
    sys.exit(main())

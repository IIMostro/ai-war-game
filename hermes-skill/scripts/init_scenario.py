"""hermes-skill/scripts/init_scenario.py — Scenario initialization via LLM + persistence."""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
from pathlib import Path

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_SKILL_DIR = os.path.dirname(_SCRIPT_DIR)
_LIB_DIR = os.path.join(_SKILL_DIR, "lib")
if _LIB_DIR not in sys.path:
    sys.path.insert(0, _LIB_DIR)

from db import (  # noqa: E402
    add_triple,
    create_schema,
    get_graph_path,
    insert_city,
    insert_faction,
    insert_general,
    log_event,
    upsert_state,
)
from hermes_client import (  # noqa: E402
    call_hermes,
    check_environment,
    parse_json_response,
)


class ScenarioInitError(Exception):
    """场景初始化验证失败。"""


def validate_scenario(data: dict) -> None:
    if not isinstance(data, dict):
        raise ScenarioInitError("data 不是合法 dict")

    cities = data.get("cities", [])
    generals = data.get("generals", [])
    connections = data.get("connections", [])

    if len(cities) < 3:
        raise ScenarioInitError("至少 3 座城池")

    if len(generals) < 5:
        raise ScenarioInitError("至少 5 名武将")

    city_ids = {c["id"] for c in cities}
    general_ids = {g["id"] for g in generals}

    if len(general_ids) != len(generals):
        raise ScenarioInitError("武将 ID 不唯一")

    player_generals = [g for g in generals if g.get("is_player")]
    if len(player_generals) != 1:
        raise ScenarioInitError("必须有且仅有一个 is_player: true 的武将")

    player = player_generals[0]
    if player.get("loyalty") is not None:
        raise ScenarioInitError("玩家武将的 loyalty 必须为 null")

    for g in generals:
        pos = g.get("position")
        if pos not in city_ids:
            raise ScenarioInitError(
                f"武将 {g['id']} 的 position '{pos}' 引用不存在的城池"
            )

        for stat in ("war", "command", "intel", "politics", "charm"):
            val = g.get(stat)
            if not isinstance(val, int) or val < 1 or val > 100:
                raise ScenarioInitError(
                    f"武将 {g['id']} 的 {stat} 值 {val} 超出范围 1-100"
                )

        troops = g.get("troops")
        if not isinstance(troops, int) or troops < 100 or troops > 100000:
            raise ScenarioInitError(
                f"武将 {g['id']} 的 troops {troops} 超出范围 100-100000"
            )

        food = g.get("food")
        if not isinstance(food, int) or food < 1 or food > 365:
            raise ScenarioInitError(
                f"武将 {g['id']} 的 food {food} 超出范围 1-365"
            )

        if not g.get("is_player"):
            loy = g.get("loyalty")
            if loy is not None and (not isinstance(loy, int) or loy < 1 or loy > 100):
                raise ScenarioInitError(
                    f"武将 {g['id']} 的 loyalty={loy} 必须为 null 或 1-100"
                )

    for conn in connections:
        from_id = conn.get("from")
        to_id = conn.get("to")
        if from_id not in city_ids:
            raise ScenarioInitError(
                f"connection from '{from_id}' 引用不存在的城池"
            )
        if to_id not in city_ids:
            raise ScenarioInitError(
                f"connection to '{to_id}' 引用不存在的城池"
            )


def build_scenario_prompt(theme: str, player_name: str) -> str:
    prompt_path = os.path.join(_SCRIPT_DIR, "init_prompt.txt")
    with open(prompt_path) as f:
        template = f.read()
    result = template.replace("{theme}", theme)
    result = result.replace("{player_name}", player_name)
    return result


def build_soul_content(general: dict, faction_name: str) -> str:
    soul_path = os.path.join(_SCRIPT_DIR, "soul_general.txt")
    with open(soul_path) as f:
        template = f.read()
    personality = general.get("personality", {})
    loyalty = general.get("loyalty")
    loyalty_display = "—" if loyalty is None else str(loyalty)
    kwargs = {
        "name": general["name"],
        "temperament": personality.get("temperament", ""),
        "faction_name": faction_name,
        "risk_preference": personality.get("risk_preference", ""),
        "battle_style": personality.get("battle_style", ""),
        "lord_attitude": personality.get("lord_attitude", ""),
        "ally_attitude": personality.get("ally_attitude", ""),
        "enemy_attitude": personality.get("enemy_attitude", ""),
        "war": general.get("war", 0),
        "cmd": general.get("command", 0),
        "intel": general.get("intel", 0),
        "politics": general.get("politics", 0),
        "charm": general.get("charm", 0),
        "loyalty_display": loyalty_display,
    }
    return template.format(**kwargs)


def create_hermes_profile(general: dict, faction_name: str) -> None:
    profile_dir = Path.home() / ".hermes" / "profiles" / general["id"]
    profile_dir.mkdir(parents=True, exist_ok=True)

    soul_content = build_soul_content(general, faction_name)
    (profile_dir / "SOUL.md").write_text(soul_content)

    (profile_dir / "MEMORY.md").write_text("")

    model = os.environ.get("AI_WAR_GAME_HERMES_MODEL", "")
    config_content = f"model: {model}\n"
    (profile_dir / "config.yaml").write_text(config_content)


def _extract_factions(data: dict) -> dict[str, str]:
    faction_ids: set[str] = set()
    for city in data.get("cities", []):
        faction_ids.add(city["owner"])
    for general in data.get("generals", []):
        faction_ids.add(general["faction"])
    if "player_identity" in data:
        faction_ids.add(data["player_identity"]["faction_id"])
    return {fid: fid for fid in sorted(faction_ids)}


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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Initialize game scenario via LLM")
    parser.add_argument("--theme", required=True, help="Scenario theme")
    parser.add_argument("--player-name", required=True, help="Player's general name")
    parser.add_argument("--db-path", default=None, help="Path to SQLite database file")
    args = parser.parse_args(argv)

    db_path = args.db_path or str(
        Path(_SCRIPT_DIR).resolve().parent.parent / "data" / "game.db"
    )
    graph_path = get_graph_path(db_path)

    os.makedirs(os.path.dirname(db_path), exist_ok=True)

    print("Checking Hermes environment...")
    check_environment()

    print("Generating scenario via LLM...")
    prompt = build_scenario_prompt(theme=args.theme, player_name=args.player_name)
    raw = call_hermes(prompt)
    scenario_data = parse_json_response(raw)

    print("Validating scenario...")
    validate_scenario(scenario_data)

    print("Creating Hermes profiles...")
    factions = _extract_factions(scenario_data)
    for g in scenario_data["generals"]:
        faction_name = factions.get(g["faction"], g["faction"])
        create_hermes_profile(g, faction_name)

    print("Persisting scenario to database...")
    conn = sqlite3.connect(db_path)
    try:
        create_schema(conn)

        for fid, fname in factions.items():
            insert_faction(conn, fid, fname)

        for city in scenario_data["cities"]:
            insert_city(
                conn,
                city["id"],
                city["name"],
                city["x"],
                city["y"],
                city["terrain"],
                city["owner"],
            )

        for g in scenario_data["generals"]:
            mapped = _map_general_for_db(g)
            insert_general(conn, mapped)

        state = scenario_data.get("initial_state", {})
        upsert_state(conn, "current_day", str(state.get("day", 1)), 1)
        upsert_state(conn, "season", state.get("season", "春"), 1)
        upsert_state(conn, "weather", state.get("weather", "晴"), 1)
        upsert_state(
            conn, "scenario_name", scenario_data.get("scenario", ""), 1
        )
        upsert_state(
            conn,
            "player_identity",
            json.dumps(scenario_data.get("player_identity", {}), ensure_ascii=False),
            1,
        )

        log_event(
            conn,
            1,
            1,
            "scenario_start",
            scenario_data["player_identity"]["id"],
            None,
            json.dumps(
                {"scenario": scenario_data.get("scenario", ""), "theme": args.theme},
                ensure_ascii=False,
            ),
        )

        if graph_path and not os.path.isfile(graph_path):
            with open(graph_path, "w") as gf:
                json.dump([], gf)

        for conn_data in scenario_data.get("connections", []):
            add_triple(
                graph_path,
                conn_data["from"],
                "connects",
                conn_data["to"],
                {"distance": conn_data["distance"]},
            )

        for rel in scenario_data.get("relationships", []):
            add_triple(
                graph_path,
                rel["subject"],
                rel["predicate"],
                rel["object"],
                rel.get("metadata", {}),
            )
    finally:
        conn.close()

    summary = {
        "scenario": scenario_data.get("scenario"),
        "factions": list(factions.keys()),
        "cities": len(scenario_data.get("cities", [])),
        "generals": len(scenario_data.get("generals", [])),
        "player": scenario_data.get("player_identity", {}).get("display_name"),
        "db_path": db_path,
    }
    print(json.dumps(summary, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())

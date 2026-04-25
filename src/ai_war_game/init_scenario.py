"""init_scenario.py — LLM-based scenario generation and persistence."""

from __future__ import annotations

import json
import os
import sqlite3

from ai_war_game.db import (
    add_triple,
    create_schema,
    get_db_path,
    get_graph_path,
    insert_city,
    insert_faction,
    insert_general,
    log_event,
    upsert_state,
)
from ai_war_game.llm import llm_call_json

SCHEMA_HINT = json.dumps(
    {
        "scenario": "str",
        "player_identity": {"id": "str", "display_name": "str", "faction_id": "str"},
        "factions": [{"id": "str", "name": "str"}],
        "cities": [
            {
                "id": "str",
                "name": "str",
                "x": "int",
                "y": "int",
                "terrain": "str",
                "owner": "str",
            }
        ],
        "connections": [{"from": "str", "to": "str", "distance": "int"}],
        "generals": [
            {
                "id": "str",
                "name": "str",
                "war": "int",
                "command": "int",
                "intel": "int",
                "politics": "int",
                "charm": "int",
                "loyalty": "int|null",
                "troops": "int",
                "food": "int",
                "position": "str",
                "faction": "str",
                "is_player": "bool",
                "personality": {
                    "temperament": "str",
                    "battle_style": "str",
                    "risk_preference": "str",
                    "lord_attitude": "str",
                    "ally_attitude": "str",
                    "enemy_attitude": "str",
                },
            }
        ],
        "relationships": [{"subject": "str", "predicate": "str", "object": "str", "metadata": {}}],
        "initial_state": {"day": "int", "season": "str", "weather": "str"},
    },
    ensure_ascii=False,
)

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
    """Build faction_id to faction_name mapping."""
    faction_names: dict[str, str] = {}
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
        upsert_state(conn, "season", state.get("season", "\u6625"), 1)
        upsert_state(conn, "weather", state.get("weather", "\u6674"), 1)
        upsert_state(conn, "scenario_name", scenario_data.get("scenario", ""), 1)
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
                {"scenario": scenario_data.get("scenario", ""), "theme": "auto"},
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

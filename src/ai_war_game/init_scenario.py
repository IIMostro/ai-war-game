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
from ai_war_game.llm import get_scenario_model, llm_call_json

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
                "terrain": "str (平原|山地|水域|森林)",
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

SYSTEM_PROMPT = """You are a Three Kingdoms scenario generator.
Theme is Chinese Three Kingdoms era. Use Chinese names for cities, factions, generals.
At least 3 cities, 5 generals. terrain must be one of: 平原, 山地, 水域, 森林.
war/cmd/intel/politics/charm: 1-100. troops: 100-100000. food: 1-365.
loyalty: null for is_player=true, 1-100 for others.
Exactly one general with is_player=true."""


def generate_scenario(theme: str, player_name: str) -> dict:
    """Generate scenario via LLM and return parsed JSON."""
    user_message = f"Theme: {theme}\nPlayer's chosen identity: {player_name}"
    return llm_call_json(
        SYSTEM_PROMPT,
        user_message,
        json_schema_hint=SCHEMA_HINT,
        model=get_scenario_model(),
    )


def _extract_factions(data: dict) -> dict[str, str]:
    """Build faction_id to faction_name mapping."""
    faction_names: dict[str, str] = {}
    for f in data.get("factions", []):
        fid = str(f.get("id", "")).strip()
        fname = str(f.get("name", fid)).strip()
        if fid:
            faction_names[fid] = fname
    for city in data.get("cities", []):
        owner = str(city.get("owner", "")).strip()
        if owner and owner not in faction_names:
            faction_names[owner] = owner
    for general in data.get("generals", []):
        f = str(general.get("faction", "")).strip()
        if f and f not in faction_names:
            faction_names[f] = f
    if "player_identity" in data:
        fid = str(data["player_identity"].get("faction_id", "")).strip()
        if fid and fid not in faction_names:
            faction_names[fid] = fid
    return faction_names


def _clamp(val, lo, hi, default):
    """Parse val to int and clamp between lo-hi. Return default on failure."""
    try:
        return max(lo, min(hi, int(val)))
    except (ValueError, TypeError):
        return default


def _map_general_for_db(g: dict) -> dict:
    raw_loyalty = g.get("loyalty")
    if raw_loyalty is None or raw_loyalty == 0 or raw_loyalty == "" or raw_loyalty == "null":
        loyalty = None
    else:
        try:
            loyalty = max(1, min(100, int(raw_loyalty)))
        except (ValueError, TypeError):
            loyalty = None
    return {
        "id": str(g.get("id", "")).strip(),
        "name": str(g.get("name", "")).strip(),
        "war": _clamp(g.get("war"), 1, 100, 50),
        "cmd": _clamp(g.get("command"), 1, 100, 50),
        "intel": _clamp(g.get("intel"), 1, 100, 50),
        "politics": _clamp(g.get("politics"), 1, 100, 50),
        "charm": _clamp(g.get("charm"), 1, 100, 50),
        "loyalty": loyalty,
        "troops": _clamp(g.get("troops"), 100, 100000, 5000),
        "food": _clamp(g.get("food"), 1, 365, 30),
        "position_city_id": str(g.get("position", "")).strip(),
        "faction_id": str(g.get("faction", "")).strip(),
        "is_player": bool(g.get("is_player", False)),
        "personality": json.dumps(g.get("personality", {}), ensure_ascii=False),
    }


def persist_scenario(db_path: str, scenario_data: dict) -> dict:
    """Persist generated scenario to SQLite + graph.json."""
    graph_path = get_graph_path(db_path)
    os.makedirs(os.path.dirname(db_path), exist_ok=True)

    allowed_terrains = {"平原", "山地", "水域", "森林"}

    conn = sqlite3.connect(db_path)
    try:
        create_schema(conn)

        factions = _extract_factions(scenario_data)
        for fid, fname in factions.items():
            insert_faction(conn, fid.strip(), fname.strip())

        # Bugfix: sync player_identity.id with the actual is_player general's ID
        # LLM may generate different IDs for player_identity vs the general entry
        for g in scenario_data.get("generals", []):
            if g.get("is_player"):
                actual_id = str(g.get("id", "")).strip()
                if actual_id:
                    scenario_data.setdefault("player_identity", {})["id"] = actual_id
                break

        for city in scenario_data.get("cities", []):
            terrain = str(city.get("terrain", "平原")).strip()
            if terrain not in allowed_terrains:
                terrain = "平原"
            insert_city(
                conn,
                str(city.get("id", "")).strip(),
                str(city.get("name", "")).strip(),
                _clamp(city.get("x"), 0, 1000, 0),
                _clamp(city.get("y"), 0, 1000, 0),
                terrain,
                str(city.get("owner", "")).strip(),
            )

        for g in scenario_data.get("generals", []):
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

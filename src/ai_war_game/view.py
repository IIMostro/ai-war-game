"""view.py — Display formatting for AI War Game."""

from __future__ import annotations

import json
import sqlite3

from ai_war_game.db import get_general, read_graph


def format_show(
    conn: sqlite3.Connection,
    faction_id: str,
    player_id: str,
    player_name: str,
) -> list[str]:
    lines: list[str] = []

    cursor = conn.execute("SELECT key, value FROM game_state")
    state = dict(cursor.fetchall())

    scenario_name = state.get("scenario_name", "")
    current_day = state.get("current_day", "?")
    season = state.get("season", "?")
    weather = state.get("weather", "?")

    cursor = conn.execute("SELECT name FROM factions WHERE id=?", (faction_id,))
    faction_row = cursor.fetchone()
    faction_display = faction_row[0] if faction_row else faction_id

    lines.append(f"\u3010{scenario_name}\u3011")
    lines.append(f"\u4f60\u662f{player_name}\uff0c{faction_display}\u4e4b\u4e3b\u3002")
    lines.append(f"\u7b2c {current_day} \u5929 \u00b7 {season} \u00b7 {weather}")
    lines.append("")

    cursor = conn.execute(
        "SELECT id, name, troops, food, position_city_id"
        " FROM generals WHERE faction_id=? AND id!=?",
        (faction_id, player_id),
    )
    subordinates = cursor.fetchall()
    if subordinates:
        lines.append(f"\u5e62\u4e0b\u6b66\u5c06 ({len(subordinates)} \u4eba)\uff1a")
        for row in subordinates:
            _gid, name, troops, food, city = row
            cursor2 = conn.execute("SELECT name FROM cities WHERE id=?", (city,))
            city_row = cursor2.fetchone()
            city_name = city_row[0] if city_row else city
            lines.append(
                f"  {name}  \u5175 {troops} \u00b7 \u7cae {food} \u65e5 \u00b7 {city_name}"
            )
        lines.append("")

    cursor = conn.execute(
        "SELECT name FROM cities WHERE owner_faction_id=?",
        (faction_id,),
    )
    city_names = [row[0] for row in cursor.fetchall()]
    if city_names:
        lines.append(f"\u57ce\u6c60: {', '.join(city_names)}")

    cursor = conn.execute(
        "SELECT COUNT(*) FROM events_log WHERE game_day=?",
        (int(current_day),),
    )
    today_events = cursor.fetchone()[0]
    lines.append(f"\u672c\u65e5\u4e8b\u4ef6: {today_events} \u6761")

    return lines


def format_general(
    conn: sqlite3.Connection,
    general_id: str,
) -> list[str]:
    general = get_general(conn, general_id)
    if general is None:
        return [f"\u6b66\u5c06 {general_id} \u672a\u627e\u5230"]

    lines: list[str] = []
    name = general["name"]
    faction_id = general["faction_id"]
    city_id = general["position_city_id"]

    cursor = conn.execute("SELECT name FROM factions WHERE id=?", (faction_id,))
    faction_row = cursor.fetchone()
    faction_name = faction_row[0] if faction_row else faction_id

    cursor = conn.execute("SELECT name FROM cities WHERE id=?", (city_id,))
    city_row = cursor.fetchone()
    city_name = city_row[0] if city_row else city_id

    lines.append(f"\u3010{name}\u3011")
    lines.append(f"\u52bf\u529b: {faction_name}")
    lines.append(f"\u6240\u5728\u5730: {city_name}")
    lines.append("")
    lines.append(f"\u6b66\u529b: {general['war']}")
    lines.append(f"\u7edf\u5e05: {general['cmd']}")
    lines.append(f"\u667a\u529b: {general['intel']}")
    lines.append(f"\u653f\u6cbb: {general['politics']}")
    lines.append(f"\u9b45\u529b: {general['charm']}")
    lines.append("")

    loyalty = general["loyalty"]
    is_player = bool(general["is_player"])
    if is_player:
        lines.append("\u5fe0\u8bda: \u2014 (\u73a9\u5bb6)")
    else:
        lines.append(f"\u5fe0\u8bda: {loyalty}")

    lines.append(f"\u5175\u529b: {general['troops']}")
    lines.append(f"\u7cae\u8349: {general['food']} \u65e5")

    try:
        personality = json.loads(general["personality"])
    except (json.JSONDecodeError, TypeError):
        personality = {}
    if personality:
        lines.append("")
        if "temperament" in personality:
            lines.append(f"\u6027\u683c: {personality['temperament']}")
        if "battle_style" in personality:
            lines.append(f"\u4f5c\u6218\u98ce\u683c: {personality['battle_style']}")
        if "risk_preference" in personality:
            lines.append(f"\u98ce\u9669\u504f\u597d: {personality['risk_preference']}")
        if "lord_attitude" in personality:
            lines.append(f"\u5bf9\u4e3b\u6001\u5ea6: {personality['lord_attitude']}")

    return lines


def format_map(conn: sqlite3.Connection, graph_path: str = "") -> list[str]:
    lines: list[str] = []
    cursor = conn.execute(
        """SELECT c.id, c.name, c.x, c.y, c.terrain, COALESCE(f.name, '\u65e0\u4e3b')
           FROM cities c
           LEFT JOIN factions f ON c.owner_faction_id = f.id
           ORDER BY c.name""",
    )
    rows = cursor.fetchall()
    if not rows:
        lines.append("(\u65e0\u57ce\u6c60)")
        return lines

    connections: dict[str, list[tuple[str, int]]] = {}
    if graph_path:
        try:
            graph = read_graph(graph_path)
            for triple in graph:
                s, p, o = triple[0], triple[1], triple[2]
                meta = triple[3] if len(triple) > 3 else {}
                if p == "connects":
                    dist = meta.get("distance", "?")
                    connections.setdefault(s, []).append((o, dist))
                    connections.setdefault(o, []).append((s, dist))
        except (FileNotFoundError, json.JSONDecodeError):
            pass

    lines.append("\u3010\u5730\u56fe\u3011")
    lines.append("")

    city_names: dict[str, str] = {row[0]: row[1] for row in rows}

    for row in rows:
        cid, name, x, y, terrain, owner = row
        lines.append(f"  {name}  ({x}, {y})  {terrain}  [{owner}]")
        if cid in connections:
            conn_lines = []
            for neighbor_id, dist in connections[cid]:
                nname = city_names.get(neighbor_id, neighbor_id)
                conn_lines.append(f"    \u2502  {nname}  ({dist}\u65e5)")
            if conn_lines:
                lines.extend(conn_lines)
    return lines


def format_events(events: list[dict]) -> list[str]:
    lines: list[str] = []
    if not events:
        lines.append("(\u65e0\u4e8b\u4ef6)")
        return lines

    lines.append("\u3010\u4e8b\u4ef6\u3011")
    for ev in events:
        day = ev.get("game_day", "?")
        seq = ev.get("seq", "?")
        etype = ev.get("event_type", "?")
        actor = ev.get("actor_id", "")
        details = ev.get("details_json", "{}")
        try:
            details_obj = json.loads(details) if isinstance(details, str) else details
        except (json.JSONDecodeError, TypeError):
            details_obj = {}
        detail_str = ""
        if isinstance(details_obj, dict):
            vals = [str(v) for v in details_obj.values() if v is not None]
            if vals:
                detail_str = " \u2014 " + ", ".join(vals)
        actor_str = f" ({actor})" if actor else ""
        lines.append(f"  \u7b2c{day}\u65e5 \u0023{seq} [{etype}]{actor_str}{detail_str}")
    return lines

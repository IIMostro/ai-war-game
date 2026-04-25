"""hermes-skill/scripts/view.py — Display formatting for AI War Game Hermes Skill."""

from __future__ import annotations

import argparse
import json
import sqlite3

from db import get_db_path, get_events, get_general


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

    lines.append(f"【{scenario_name}】")
    lines.append(f"你是{player_name}，{faction_display}之主。")  # noqa: RUF001
    lines.append(f"第 {current_day} 天 · {season} · {weather}")
    lines.append("")

    cursor = conn.execute(
        "SELECT id, name, troops, food, position_city_id"
        " FROM generals WHERE faction_id=? AND id!=?",
        (faction_id, player_id),
    )
    subordinates = cursor.fetchall()
    if subordinates:
        lines.append(f"麾下武将 ({len(subordinates)} 人)：")  # noqa: RUF001
        for row in subordinates:
            _gid, name, troops, food, city = row
            cursor2 = conn.execute("SELECT name FROM cities WHERE id=?", (city,))
            city_row = cursor2.fetchone()
            city_name = city_row[0] if city_row else city
            lines.append(f"  {name}  兵 {troops} · 粮 {food} 日 · {city_name}")
        lines.append("")

    cursor = conn.execute(
        "SELECT name FROM cities WHERE owner_faction_id=?",
        (faction_id,),
    )
    city_names = [row[0] for row in cursor.fetchall()]
    if city_names:
        lines.append(f"城池: {', '.join(city_names)}")

    cursor = conn.execute(
        "SELECT COUNT(*) FROM events_log WHERE game_day=?",
        (int(current_day),),
    )
    today_events = cursor.fetchone()[0]
    lines.append(f"本日事件: {today_events} 条")

    return lines


def format_general(
    conn: sqlite3.Connection,
    general_id: str,
) -> list[str]:
    general = get_general(conn, general_id)
    if general is None:
        return [f"武将 {general_id} 未找到"]

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

    lines.append(f"【{name}】")
    lines.append(f"势力: {faction_name}")
    lines.append(f"所在地: {city_name}")
    lines.append("")
    lines.append(f"武力: {general['war']}")
    lines.append(f"统帅: {general['cmd']}")
    lines.append(f"智力: {general['intel']}")
    lines.append(f"政治: {general['politics']}")
    lines.append(f"魅力: {general['charm']}")
    lines.append("")

    loyalty = general["loyalty"]
    is_player = bool(general["is_player"])
    if is_player:
        lines.append("忠诚: — (玩家)")
    else:
        lines.append(f"忠诚: {loyalty}")

    lines.append(f"兵力: {general['troops']}")
    lines.append(f"粮草: {general['food']} 日")

    try:
        personality = json.loads(general["personality"])
    except (json.JSONDecodeError, TypeError):
        personality = {}
    if personality:
        lines.append("")
        if "temperament" in personality:
            lines.append(f"性格: {personality['temperament']}")
        if "battle_style" in personality:
            lines.append(f"作战风格: {personality['battle_style']}")
        if "risk_preference" in personality:
            lines.append(f"风险偏好: {personality['risk_preference']}")
        if "lord_attitude" in personality:
            lines.append(f"对主态度: {personality['lord_attitude']}")

    return lines


def format_map(conn: sqlite3.Connection) -> list[str]:
    lines: list[str] = []
    cursor = conn.execute(
        """SELECT c.name, c.x, c.y, c.terrain, COALESCE(f.name, '无主')
           FROM cities c
           LEFT JOIN factions f ON c.owner_faction_id = f.id
           ORDER BY c.name""",
    )
    rows = cursor.fetchall()
    if not rows:
        lines.append("(无城池)")
        return lines

    lines.append("【地图】")
    lines.append("")
    for row in rows:
        name, x, y, terrain, owner = row
        lines.append(f"  {name}  ({x}, {y})  {terrain}  [{owner}]")
    return lines


def format_events(events: list[dict]) -> list[str]:
    lines: list[str] = []
    if not events:
        lines.append("(无事件)")
        return lines

    lines.append("【事件】")
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
                detail_str = " — " + ", ".join(vals)
        actor_str = f" ({actor})" if actor else ""
        lines.append(f"  第{day}日 #{seq} [{etype}]{actor_str}{detail_str}")
    return lines


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="AI War Game View Layer")
    parser.add_argument("--db-path", default=None, help="Path to SQLite database file")
    sub = parser.add_subparsers(dest="command", required=True)

    show_parser = sub.add_parser("show", help="Print formatted situation summary")
    show_parser.add_argument("--db-path", dest="show_db_path", default=None)

    general_parser = sub.add_parser("general", help="Print general detail panel")
    general_parser.add_argument("id")
    general_parser.add_argument("--db-path", dest="general_db_path", default=None)

    map_parser = sub.add_parser("map", help="Print ASCII map")
    map_parser.add_argument("--db-path", dest="map_db_path", default=None)

    events_parser = sub.add_parser("events", help="Print recent events")
    events_parser.add_argument("--limit", type=int, default=10)
    events_parser.add_argument("--db-path", dest="events_db_path", default=None)

    args = parser.parse_args(argv)

    db_path = ""

    if args.command == "show":
        db_path = get_db_path(getattr(args, "show_db_path", None), __file__)
        conn = sqlite3.connect(db_path)
        cursor = conn.execute("SELECT value FROM game_state WHERE key='player_identity'")
        row = cursor.fetchone()
        if row is None:
            print("错误: 未找到玩家身份")
            conn.close()
            return 1
        player_id = row[0]

        general = get_general(conn, player_id)
        if general is None:
            print(f"错误: 未找到武将 {player_id}")
            conn.close()
            return 1

        player_name = general["name"]
        faction_id = general["faction_id"]

        lines = format_show(conn, faction_id, player_id, player_name)
        conn.close()
        print("\n".join(lines))

    elif args.command == "general":
        db_path = get_db_path(getattr(args, "general_db_path", None), __file__)
        conn = sqlite3.connect(db_path)
        lines = format_general(conn, args.id)
        conn.close()
        print("\n".join(lines))

    elif args.command == "map":
        db_path = get_db_path(getattr(args, "map_db_path", None), __file__)
        conn = sqlite3.connect(db_path)
        lines = format_map(conn)
        conn.close()
        print("\n".join(lines))

    elif args.command == "events":
        db_path = get_db_path(getattr(args, "events_db_path", None), __file__)
        conn = sqlite3.connect(db_path)
        events = get_events(conn, limit=args.limit)
        conn.close()
        lines = format_events(events)
        print("\n".join(lines))

    return 0


if __name__ == "__main__":
    main()

"""Time engine and event system for AI War Game."""

from __future__ import annotations

import argparse
import heapq
import json
import os
import random
import sqlite3
from pathlib import Path

from db import (
    get_db_path,
    get_graph_path,
    log_event,
    read_graph,
    upsert_state,
)


def get_event_queue_path(db_path: str) -> str:
    db = Path(db_path)
    return str(db.with_name("event_queue.json"))


def load_event_queue(queue_path: str) -> list[list]:
    if not os.path.exists(queue_path):
        return []
    with open(queue_path, encoding="utf-8") as f:
        return list(json.load(f))


def save_event_queue(queue_path: str, queue: list) -> None:
    with open(queue_path, "w", encoding="utf-8") as f:
        json.dump(queue, f, ensure_ascii=False)


def schedule_event(
    queue_path: str,
    day: int,
    priority: int,
    event_type: str,
    actor_id: str | None = None,
    target_id: str | None = None,
    details: dict | None = None,
) -> None:
    if details is None:
        details = {}
    queue = load_event_queue(queue_path)
    heapq.heappush(queue, [day, priority, event_type, actor_id, target_id, details])
    save_event_queue(queue_path, queue)


def calc_season(day: int) -> str:
    mapping = ["春", "夏", "秋", "冬"]
    return mapping[(day // 30) % 4]


def generate_weather(season: str) -> str:
    pool = {
        "春": ["晴", "雨", "阴"],
        "夏": ["晴", "雨", "阴", "雨"],
        "秋": ["晴", "阴", "雨"],
        "冬": ["晴", "阴", "雪"],
    }
    return random.choice(pool.get(season, ["晴"]))


def march_days(graph_path: str, from_city: str, to_city: str) -> int | None:
    try:
        graph = read_graph(graph_path)
    except (FileNotFoundError, json.JSONDecodeError):
        return None
    for triple in graph:
        s, p, o = triple[0], triple[1], triple[2]
        meta = triple[3] if len(triple) > 3 else {}
        if s == from_city and o == to_city and p == "connects":
            return meta.get("distance")
    return None


def consume_food(conn: sqlite3.Connection, general_id: str, days: int) -> None:
    cursor = conn.execute("SELECT food FROM generals WHERE id=?", (general_id,))
    row = cursor.fetchone()
    if row is None:
        return
    new_food = max(1, row[0] - days)
    conn.execute("UPDATE generals SET food = ? WHERE id = ?", (new_food, general_id))
    conn.commit()


def consume_all_food(conn: sqlite3.Connection, days: int) -> list[dict]:
    cursor = conn.execute("SELECT id, food, name FROM generals")
    starving = []
    for row in cursor.fetchall():
        gid, food, name = row
        new_food = max(1, food - days)
        conn.execute("UPDATE generals SET food = ? WHERE id = ?", (new_food, gid))
        if food - days <= 0:
            starving.append({"general_id": gid, "name": name, "food": new_food})
    conn.commit()
    return starving


def run_daily_checks(conn: sqlite3.Connection, day: int) -> list[dict]:
    events: list[dict] = []
    cursor = conn.execute("SELECT id, food, name FROM generals")
    for row in cursor.fetchall():
        gid, food, name = row
        if food < 2:
            events.append(
                {
                    "day": day,
                    "event_type": "food_critical",
                    "actor_id": gid,
                    "target_id": None,
                    "details": {"food": food, "name": name},
                }
            )
        elif food < 5:
            events.append(
                {
                    "day": day,
                    "event_type": "food_warning",
                    "actor_id": gid,
                    "target_id": None,
                    "details": {"food": food, "name": name},
                }
            )
    return events


def process_due_events(
    conn: sqlite3.Connection,
    queue_path: str,
    graph_path: str,
) -> list[dict]:
    cursor = conn.execute("SELECT value FROM game_state WHERE key='current_day'")
    row = cursor.fetchone()
    current_day = int(row[0]) if row else 1

    queue = load_event_queue(queue_path)
    heapq.heapify(queue)

    processed: list[list] = []
    while queue and queue[0][0] <= current_day:
        processed.append(heapq.heappop(queue))

    save_event_queue(queue_path, queue)

    result: list[dict] = []
    for seq, event in enumerate(processed, start=1):
        day, priority, event_type, actor_id, target_id, details = event
        log_event(
            conn,
            day,
            seq,
            event_type,
            actor_id,
            target_id,
            json.dumps(details, ensure_ascii=False),
        )
        result.append(
            {
                "day": day,
                "priority": priority,
                "event_type": event_type,
                "actor_id": actor_id,
                "target_id": target_id,
                "details": details,
            }
        )

    return result


def advance_time(
    conn: sqlite3.Connection,
    queue_path: str,
    graph_path: str,
    days: int,
) -> list[dict]:
    all_events: list[dict] = []
    for _ in range(days):
        cursor = conn.execute("SELECT value FROM game_state WHERE key='current_day'")
        current_day = int(cursor.fetchone()[0])
        new_day = current_day + 1

        upsert_state(conn, "current_day", str(new_day), new_day)

        if new_day % 30 == 0:
            new_season = calc_season(new_day)
            upsert_state(conn, "season", new_season, new_day)

        cursor = conn.execute("SELECT value FROM game_state WHERE key='season'")
        season = cursor.fetchone()[0]
        weather = generate_weather(season)
        upsert_state(conn, "weather", weather, new_day)

        consume_all_food(conn, 1)

        all_events.extend(run_daily_checks(conn, new_day))
        all_events.extend(process_due_events(conn, queue_path, graph_path))

    return all_events


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="AI War Game Time Engine & Event System")
    parser.add_argument("--db-path", default=None, help="Path to SQLite database file")
    sub = parser.add_subparsers(dest="command", required=True)

    advance_parser = sub.add_parser("advance", help="Advance N days and process events")
    advance_parser.add_argument("--days", type=int, required=True)
    advance_parser.add_argument("--db-path", dest="advance_db_path", default=None)

    schedule_parser = sub.add_parser("schedule", help="Schedule a future event")
    schedule_parser.add_argument("--day", type=int, required=True)
    schedule_parser.add_argument("--type", required=True, dest="event_type")
    schedule_parser.add_argument("--actor", default=None)
    schedule_parser.add_argument("--target", default=None)
    schedule_parser.add_argument("--details", default="{}")
    schedule_parser.add_argument("--db-path", dest="schedule_db_path", default=None)

    queue_parser = sub.add_parser("show-queue", help="Show pending events")
    queue_parser.add_argument("--db-path", dest="queue_db_path", default=None)

    weather_parser = sub.add_parser("weather", help="Generate and show today's weather")
    weather_parser.add_argument("--db-path", dest="weather_db_path", default=None)

    p_march = sub.add_parser("march-days", help="Calculate march days between cities")
    p_march.add_argument("--from", dest="from_city", required=True)
    p_march.add_argument("--to", dest="to_city", required=True)
    p_march.add_argument("--db-path", dest="db_path_arg")

    args = parser.parse_args(argv)

    if args.command == "advance":
        db_path = get_db_path(getattr(args, "advance_db_path", None), __file__)
        queue_path = get_event_queue_path(db_path)
        graph_path = get_graph_path(db_path)
        conn = sqlite3.connect(db_path)
        events = advance_time(conn, queue_path, graph_path, args.days)
        conn.close()
        print(json.dumps(events, ensure_ascii=False))

    elif args.command == "schedule":
        db_path = get_db_path(getattr(args, "schedule_db_path", None), __file__)
        queue_path = get_event_queue_path(db_path)
        details = json.loads(args.details)
        schedule_event(queue_path, args.day, 0, args.event_type, args.actor, args.target, details)

    elif args.command == "show-queue":
        db_path = get_db_path(getattr(args, "queue_db_path", None), __file__)
        queue_path = get_event_queue_path(db_path)
        queue = load_event_queue(queue_path)
        print(json.dumps(queue, ensure_ascii=False))

    elif args.command == "weather":
        db_path = get_db_path(getattr(args, "weather_db_path", None), __file__)
        conn = sqlite3.connect(db_path)
        cursor = conn.execute("SELECT value FROM game_state WHERE key='season'")
        row = cursor.fetchone()
        if row is None:
            print('{"error": "no season found"}')
            conn.close()
            return 1
        season = row[0]
        weather = generate_weather(season)
        print(json.dumps({"season": season, "weather": weather}, ensure_ascii=False))
        conn.close()

    elif args.command == "march-days":
        graph_path = get_graph_path(get_db_path(getattr(args, "db_path_arg", None), __file__))
        days = march_days(graph_path, args.from_city, args.to_city)
        result = {"from": args.from_city, "to": args.to_city}
        if days is not None:
            result["days"] = days
        else:
            result["error"] = "未找到连接"
        print(json.dumps(result, ensure_ascii=False))
        return 0

    return 0


if __name__ == "__main__":
    main()

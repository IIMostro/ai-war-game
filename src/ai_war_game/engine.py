"""engine.py — Time engine and event system for AI War Game."""

from __future__ import annotations

import heapq
import json
import os
import random
import sqlite3
from pathlib import Path

from ai_war_game.db import get_graph_path, log_event, read_graph, upsert_state


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
    mapping = ["\u6625", "\u590f", "\u79cb", "\u51ac"]
    return mapping[(day // 30) % 4]


def generate_weather(season: str) -> str:
    pool = {
        "\u6625": ["\u6674", "\u96e8", "\u9634"],
        "\u590f": ["\u6674", "\u96e8", "\u9634", "\u96e8"],
        "\u79cb": ["\u6674", "\u9634", "\u96e8"],
        "\u51ac": ["\u6674", "\u9634", "\u96ea"],
    }
    return random.choice(pool.get(season, ["\u6674"]))


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

"""tests/unit/hermes_skill/test_time_engine.py"""

import json
import sqlite3
import subprocess

import pytest

from db import create_schema, insert_city, insert_faction, insert_general, upsert_state
from time_engine import (
    advance_time,
    calc_season,
    consume_food,
    generate_weather,
    load_event_queue,
    march_days,
    process_due_events,
    run_daily_checks,
    schedule_event,
)


@pytest.fixture
def conn(tmp_path):
    db = tmp_path / "test.db"
    c = sqlite3.connect(str(db))
    create_schema(c)
    insert_faction(c, "wei", "曹魏")
    insert_city(c, "luoyang", "洛阳", 0, 0, "平原", "wei")
    insert_city(c, "yingchuan", "颍川", 5, 3, "平原", "wei")
    insert_general(
        c,
        {
            "id": "caocao",
            "name": "曹操",
            "war": 72,
            "cmd": 86,
            "intel": 91,
            "politics": 88,
            "charm": 80,
            "loyalty": None,
            "troops": 8000,
            "food": 15,
            "position_city_id": "luoyang",
            "faction_id": "wei",
            "is_player": True,
            "personality": "{}",
        },
    )
    insert_general(
        c,
        {
            "id": "xiahou",
            "name": "夏侯惇",
            "war": 90,
            "cmd": 82,
            "intel": 60,
            "politics": 50,
            "charm": 70,
            "loyalty": 95,
            "troops": 5000,
            "food": 3,
            "position_city_id": "luoyang",
            "faction_id": "wei",
            "is_player": False,
            "personality": "{}",
        },
    )
    upsert_state(c, "current_day", "1", 1)
    upsert_state(c, "season", "春", 1)
    upsert_state(c, "weather", "晴", 1)
    yield c
    c.close()


@pytest.fixture
def graph_with_connection(tmp_path):
    g = tmp_path / "graph.json"
    data = [["luoyang", "connects", "yingchuan", {"distance": 5}]]
    g.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return str(g)


class TestCalcSeason:
    def test_day_1_is_spring(self):
        assert calc_season(1) == "春"

    def test_day_31_is_summer(self):
        assert calc_season(31) == "夏"

    def test_day_61_is_autumn(self):
        assert calc_season(61) == "秋"

    def test_day_91_is_winter(self):
        assert calc_season(91) == "冬"

    def test_day_121_is_spring_again(self):
        assert calc_season(121) == "春"


class TestGenerateWeather:
    def test_returns_valid_weather(self):
        weather = generate_weather("春")
        assert weather in ("晴", "雨", "阴")

    def test_winter_can_snow(self):
        weathers = set()
        for _ in range(100):
            weathers.add(generate_weather("冬"))
        assert "雪" in weathers


class TestScheduleAndQueue:
    def test_schedule_and_load(self, tmp_path):
        q_file = tmp_path / "queue.json"
        q_file.write_text("[]", encoding="utf-8")
        schedule_event(str(q_file), 5, 0, "arrival", "liubei", "yingchuan", {"from": "luoyang"})
        queue = load_event_queue(str(q_file))
        assert len(queue) == 1
        assert queue[0][2] == "arrival"

    def test_heap_order_by_day_then_priority(self, tmp_path):
        q_file = tmp_path / "queue.json"
        q_file.write_text("[]", encoding="utf-8")
        schedule_event(str(q_file), 10, 0, "later", None, None)
        schedule_event(str(q_file), 5, 0, "earlier", None, None)
        queue = load_event_queue(str(q_file))
        import heapq

        first = heapq.heappop(queue)
        assert first[2] == "earlier"


class TestAdvanceTime:
    def test_advances_current_day(self, conn, tmp_path, graph_with_connection):
        q_file = tmp_path / "queue.json"
        q_file.write_text("[]", encoding="utf-8")
        advance_time(conn, str(q_file), graph_with_connection, days=3)
        cursor = conn.execute("SELECT value FROM game_state WHERE key='current_day'")
        assert cursor.fetchone()[0] == "4"

    def test_updates_season_at_day_30(self, conn, tmp_path, graph_with_connection):
        conn.execute("UPDATE game_state SET value='29' WHERE key='current_day'")
        q_file = tmp_path / "queue.json"
        q_file.write_text("[]", encoding="utf-8")
        advance_time(conn, str(q_file), graph_with_connection, days=2)
        cursor = conn.execute("SELECT value FROM game_state WHERE key='season'")
        assert cursor.fetchone()[0] == "夏"

    def test_logs_weather_change(self, conn, tmp_path, graph_with_connection):
        q_file = tmp_path / "queue.json"
        q_file.write_text("[]", encoding="utf-8")
        advance_time(conn, str(q_file), graph_with_connection, days=1)
        cursor = conn.execute("SELECT value FROM game_state WHERE key='weather'")
        weather = cursor.fetchone()[0]
        assert weather in ("晴", "雨", "阴", "雪")


class TestFood:
    def test_consumes_food_daily(self, conn, tmp_path, graph_with_connection):
        q_file = tmp_path / "queue.json"
        q_file.write_text("[]", encoding="utf-8")
        advance_time(conn, str(q_file), graph_with_connection, days=3)
        cursor = conn.execute("SELECT food FROM generals WHERE id='caocao'")
        assert cursor.fetchone()[0] == 12  # 15 - 3

    def test_food_warning_general(self, conn):
        events = run_daily_checks(conn, 5)
        food_warnings = [e for e in events if e["event_type"] == "food_warning"]
        assert len(food_warnings) >= 1

    def test_consume_food_specific(self, conn):
        consume_food(conn, "caocao", 5)
        cursor = conn.execute("SELECT food FROM generals WHERE id='caocao'")
        assert cursor.fetchone()[0] == 10  # 15 - 5


class TestMarchDays:
    def test_finds_connection(self, graph_with_connection):
        days = march_days(graph_with_connection, "luoyang", "yingchuan")
        assert days == 5

    def test_returns_none_for_no_connection(self, graph_with_connection):
        days = march_days(graph_with_connection, "luoyang", "nonexistent")
        assert days is None


class TestCLI:
    def test_march_days_via_main(self, graph_with_connection, tmp_path, monkeypatch):
        db_path = tmp_path / "test.db"
        monkeypatch.setattr("time_engine.get_db_path", lambda *args: str(db_path))
        monkeypatch.setattr("time_engine.get_graph_path", lambda *args: str(graph_with_connection))
        conn = sqlite3.connect(str(db_path))
        create_schema(conn)
        conn.close()
        result = subprocess.run(
            ["python3", "hermes-skill/scripts/time_engine.py", "march-days",
             "--from", "luoyang", "--to", "yingchuan",
             "--db-path", str(db_path)],
            capture_output=True, text=True,
        )
        assert result.returncode == 0
        import json
        data = json.loads(result.stdout)
        assert data["days"] == 5


class TestProcessDueEvents:
    def test_processes_due_events(self, conn, tmp_path):
        q_file = tmp_path / "queue.json"
        q_file.write_text("[]", encoding="utf-8")
        schedule_event(str(q_file), 1, 0, "test_event", "caocao", None, {"msg": "hello"})
        events = process_due_events(conn, str(q_file), str(tmp_path / "graph.json"))
        assert len(events) == 1
        assert events[0]["event_type"] == "test_event"
        cursor = conn.execute("SELECT count(*) FROM events_log WHERE event_type='test_event'")
        assert cursor.fetchone()[0] == 1

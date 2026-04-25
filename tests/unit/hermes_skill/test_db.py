"""tests/unit/hermes_skill/test_db.py"""

from __future__ import annotations

import json
import sqlite3

import pytest

from db import (
    add_triple,
    create_schema,
    get_events,
    get_state,
    init_scenario_data,
    insert_city,
    insert_faction,
    insert_general,
    log_event,
    read_graph,
    upsert_state,
)


@pytest.fixture
def conn(tmp_path):
    db = tmp_path / "test.db"
    c = sqlite3.connect(str(db))
    create_schema(c)
    yield c
    c.close()


class TestCreateSchema:
    def test_tables_exist_after_create(self, conn):
        cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
        tables = [row[0] for row in cursor.fetchall()]
        assert "factions" in tables
        assert "cities" in tables
        assert "generals" in tables
        assert "game_state" in tables
        assert "events_log" in tables


class TestFactionCRUD:
    def test_insert_and_query(self, conn):
        insert_faction(conn, "wei", "曹魏")
        cursor = conn.execute("SELECT id, name FROM factions WHERE id=?", ("wei",))
        row = cursor.fetchone()
        assert row == ("wei", "曹魏")

    def test_duplicate_id_raises(self, conn):
        insert_faction(conn, "wei", "曹魏")
        with pytest.raises(sqlite3.IntegrityError):
            insert_faction(conn, "wei", "duplicated")


class TestCityCRUD:
    def test_insert_and_query(self, conn):
        insert_faction(conn, "wei", "曹魏")
        insert_city(conn, "luoyang", "洛阳", 100, 200, "平原", "wei")
        cursor = conn.execute(
            "SELECT id, name, x, y, terrain, owner_faction_id FROM cities WHERE id=?",
            ("luoyang",),
        )
        row = cursor.fetchone()
        assert row == ("luoyang", "洛阳", 100, 200, "平原", "wei")


class TestGeneralCRUD:
    def test_insert_and_query(self, conn):
        insert_faction(conn, "wei", "曹魏")
        insert_city(conn, "luoyang", "洛阳", 0, 0, "平原", "wei")
        insert_general(
            conn,
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
                "personality": json.dumps({"temperament": "ambitious"}),
            },
        )
        cursor = conn.execute(
            "SELECT id, name, war, cmd, intel, politics, charm, troops, food, is_player"
            " FROM generals WHERE id=?",
            ("caocao",),
        )
        row = cursor.fetchone()
        assert row is not None
        assert row[0] == "caocao"

    def test_invalid_war_stat_raises(self, conn):
        insert_faction(conn, "wei", "曹魏")
        insert_city(conn, "luoyang", "洛阳", 0, 0, "平原", "wei")
        with pytest.raises(sqlite3.IntegrityError):
            insert_general(
                conn,
                {
                    "id": "bad",
                    "name": "Bad",
                    "war": 999,
                    "cmd": 50,
                    "intel": 50,
                    "politics": 50,
                    "charm": 50,
                    "loyalty": 50,
                    "troops": 5000,
                    "food": 10,
                    "position_city_id": "luoyang",
                    "faction_id": "wei",
                    "is_player": False,
                    "personality": "{}",
                },
            )


class TestGameState:
    def test_write_and_read(self, conn):
        upsert_state(conn, "current_day", "1", 1)
        upsert_state(conn, "season", "春", 1)
        states = get_state(conn)
        assert {"key": "current_day", "value": "1", "updated_day": 1} in states
        assert {"key": "season", "value": "春", "updated_day": 1} in states

    def test_upsert_overwrites(self, conn):
        upsert_state(conn, "current_day", "1", 1)
        upsert_state(conn, "current_day", "5", 5)
        states = get_state(conn)
        current_day_entries = [s for s in states if s["key"] == "current_day"]
        assert len(current_day_entries) == 1
        assert current_day_entries[0]["value"] == "5"


class TestEvents:
    def test_log_and_query(self, conn):
        log_event(conn, 1, 1, "scenario_start", None, None, "{}")
        log_event(conn, 1, 2, "general_created", "caocao", None, json.dumps({"name": "曹操"}))
        events = get_events(conn, limit=10)
        assert len(events) == 2
        assert events[0]["event_type"] == "scenario_start"
        assert events[1]["actor_id"] == "caocao"

    def test_limit(self, conn):
        for i in range(5):
            log_event(conn, 1, i, "test", None, None, "{}")
        events = get_events(conn, limit=3)
        assert len(events) == 3


class TestGraph:
    def test_read_empty_graph(self, tmp_path):
        graph_file = tmp_path / "graph.json"
        graph_file.write_text("[]")
        assert read_graph(str(graph_file)) == []

    def test_add_and_read(self, tmp_path):
        graph_file = tmp_path / "graph.json"
        graph_file.write_text("[]")
        add_triple(str(graph_file), "caocao", "serves", "han")
        triples = read_graph(str(graph_file))
        assert len(triples) == 1
        assert triples[0] == ["caocao", "serves", "han", {}]

    def test_multiple_triples(self, tmp_path):
        graph_file = tmp_path / "graph.json"
        graph_file.write_text("[]")
        add_triple(str(graph_file), "luoyang", "connects", "yingchuan", {"distance": 5})
        add_triple(str(graph_file), "caocao", "trusts", "liubei")
        triples = read_graph(str(graph_file))
        assert len(triples) == 2


class TestScenarioInit:
    def test_init_full_scenario(self, tmp_path):
        db_file = tmp_path / "test.db"
        graph_file = tmp_path / "graph.json"
        graph_file.write_text("[]")
        conn = sqlite3.connect(str(db_file))
        create_schema(conn)
        insert_faction(conn, "wei", "曹魏")
        insert_city(conn, "luoyang", "洛阳", 0, 0, "平原", "wei")
        conn.close()
        scenario = {
            "scenario_name": "黄巾之乱",
            "player_identity": "caocao",
            "state": {"current_day": 1, "season": "春", "weather": "晴"},
            "generals": [
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
                }
            ],
            "events": [{"day": 1, "type": "scenario_start", "details": "黄巾之乱开始"}],
            "graph": [["luoyang", "connects", "yingchuan", {"distance": 5}]],
        }
        init_scenario_data(str(db_file), str(graph_file), scenario)
        conn = sqlite3.connect(str(db_file))
        states = get_state(conn)
        keys = [s["key"] for s in states]
        assert "current_day" in keys
        assert "season" in keys
        conn.close()

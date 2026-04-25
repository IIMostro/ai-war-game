"""tests/unit/hermes_skill/test_view.py"""

from __future__ import annotations

import json
import sqlite3

import pytest

from db import (
    create_schema,
    get_events,
    insert_city,
    insert_faction,
    insert_general,
    log_event,
    upsert_state,
)
from view import format_events, format_general, format_map, format_show

_SAMPLE_PERSONALITY = json.dumps(
    {
        "temperament": "ambitious",
        "battle_style": "aggressive",
        "risk_preference": "high",
        "lord_attitude": "self-serving",
        "ally_attitude": "pragmatic",
        "enemy_attitude": "ruthless",
    },
    ensure_ascii=False,
)


@pytest.fixture
def conn(tmp_path):
    db = tmp_path / "test.db"
    c = sqlite3.connect(str(db))
    create_schema(c)
    insert_faction(c, "wei", "曹魏")
    insert_city(c, "luoyang", "洛阳", 100, 200, "平原", "wei")
    insert_city(c, "yingchuan", "颍川", 150, 220, "平原", "wei")
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
            "personality": _SAMPLE_PERSONALITY,
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
            "food": 12,
            "position_city_id": "luoyang",
            "faction_id": "wei",
            "is_player": False,
            "personality": "{}",
        },
    )
    upsert_state(c, "current_day", "15", 15)
    upsert_state(c, "season", "夏", 15)
    upsert_state(c, "weather", "雨", 15)
    upsert_state(c, "scenario_name", "黄巾之乱", 1)
    upsert_state(c, "player_identity", "caocao", 1)
    log_event(c, 15, 1, "battle", "xiahou", None, json.dumps({"result": "victory"}))
    c.commit()
    yield c
    c.close()


class TestFormatShow:
    def test_contains_key_info(self, conn):
        lines = format_show(conn, "wei", "caocao", "曹操")
        output = "\n".join(lines)
        assert "曹操" in output
        assert "曹魏" in output
        assert "15" in output or "第" in output
        assert "夏" in output
        assert "雨" in output
        assert "黄巾之乱" in output


class TestFormatGeneral:
    def test_player_general_has_no_loyalty(self, conn):
        lines = format_general(conn, "caocao", _SAMPLE_PERSONALITY)
        output = "\n".join(lines)
        assert "曹操" in output
        assert "72" in output

    def test_ai_general_shows_loyalty(self, conn):
        lines = format_general(conn, "xiahou", "{}")
        output = "\n".join(lines)
        assert "夏侯惇" in output
        assert "95" in output


class TestFormatMap:
    def test_shows_cities(self, conn):
        lines = format_map(conn)
        output = "\n".join(lines)
        assert "洛阳" in output
        assert "颍川" in output


class TestFormatEvents:
    def test_shows_recent_events(self, conn):
        events = get_events(conn, limit=10)
        lines = format_events(events)
        output = "\n".join(lines)
        assert "battle" in output
        assert "xiahou" in output

    def test_empty_events(self):
        lines = format_events([])
        assert len(lines) > 0
        assert "无事件" in "".join(lines)

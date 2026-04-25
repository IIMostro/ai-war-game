"""tests/unit/hermes_skill/test_game_loop.py

End-to-end integration test for the complete game loop.
Mocks Hermes subprocess calls (all external I/O).
"""

import json
import sqlite3

import pytest


@pytest.fixture
def db_path(tmp_path) -> str:
    from db import create_schema, insert_city, insert_faction, insert_general, upsert_state

    path = str(tmp_path / "game.db")
    conn = sqlite3.connect(path)
    create_schema(conn)

    insert_faction(conn, "han", "汉室")
    insert_faction(conn, "yellow", "黄巾")
    insert_city(conn, "luoyang", "洛阳", 0, 0, "平原", "han")
    insert_city(conn, "yingchuan", "颍川", 5, 3, "平原", "yellow")
    insert_city(conn, "julu", "巨鹿", 8, 5, "山地", "yellow")
    insert_general(conn, {
        "id": "caocao", "name": "曹操", "war": 72, "cmd": 86, "intel": 91,
        "politics": 88, "charm": 80, "loyalty": None, "troops": 8000, "food": 15,
        "position_city_id": "luoyang", "faction_id": "han",
        "is_player": True, "personality": "{}",
    })
    insert_general(conn, {
        "id": "xiahou", "name": "夏侯惇", "war": 90, "cmd": 82, "intel": 60,
        "politics": 50, "charm": 70, "loyalty": 95, "troops": 5000, "food": 12,
        "position_city_id": "luoyang", "faction_id": "han",
        "is_player": False, "personality": "{}",
    })
    insert_general(conn, {
        "id": "zhangjiao", "name": "张角", "war": 40, "cmd": 70, "intel": 85,
        "politics": 60, "charm": 90, "loyalty": 100, "troops": 20000, "food": 20,
        "position_city_id": "yingchuan", "faction_id": "yellow",
        "is_player": False, "personality": "{}",
    })
    upsert_state(conn, "current_day", "1", 1)
    upsert_state(conn, "season", "春", 1)
    upsert_state(conn, "weather", "晴", 1)
    upsert_state(conn, "scenario_name", "黄巾之乱", 1)
    upsert_state(conn, "player_identity", "caocao", 1)
    conn.close()
    return path


@pytest.fixture
def graph_path(tmp_path) -> str:
    p = str(tmp_path / "graph.json")
    data = [
        ["luoyang", "connects", "yingchuan", {"distance": 5}],
        ["yingchuan", "connects", "julu", {"distance": 4}],
    ]
    with open(p, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)
    return p


@pytest.fixture
def queue_path(tmp_path) -> str:
    p = str(tmp_path / "event_queue.json")
    with open(p, "w", encoding="utf-8") as f:
        json.dump([], f)
    return p


class TestFullGameLoop:
    """Verify the complete game loop: advance time -> process events -> check state."""

    def test_advance_time_reduces_food(self, db_path, queue_path, graph_path):
        import time_engine
        conn = sqlite3.connect(db_path)
        try:
            time_engine.advance_time(conn, queue_path, graph_path, days=3)
            cursor = conn.execute("SELECT food FROM generals WHERE id='caocao'")
            food = cursor.fetchone()[0]
            assert food < 15
        finally:
            conn.close()

    def test_advance_time_triggers_weather_change(self, db_path, queue_path, graph_path):
        import time_engine
        conn = sqlite3.connect(db_path)
        try:
            time_engine.advance_time(conn, queue_path, graph_path, days=1)
            cursor = conn.execute("SELECT value FROM game_state WHERE key='weather'")
            weather = cursor.fetchone()[0]
            assert weather in ("晴", "雨", "阴", "雪")
        finally:
            conn.close()

    def test_food_warning_triggers_event(self, db_path, queue_path, graph_path):
        import time_engine
        conn = sqlite3.connect(db_path)
        try:
            conn.execute("UPDATE generals SET food=3 WHERE id='xiahou'")
            conn.commit()
            events = time_engine.advance_time(conn, queue_path, graph_path, days=1)
            food_events = [e for e in events if e.get("event_type") == "food_warning"]
            assert len(food_events) >= 1
        finally:
            conn.close()

    def test_battle_flow_identify_participants(self, db_path):
        import battle
        conn = sqlite3.connect(db_path)
        try:
            participants = battle.identify_participants(conn, "caocao", "zhangjiao")
            assert participants["attacker"]["id"] == "caocao"
            assert participants["defender"]["id"] == "zhangjiao"
            assert participants["city"]["id"] == "yingchuan"
        finally:
            conn.close()

    def test_battle_apply_updates_state(self, db_path):
        import battle
        conn = sqlite3.connect(db_path)
        try:
            result = {
                "outcome": "attacker_win",
                "attacker_id": "caocao",
                "defender_id": "zhangjiao",
                "city_id": "yingchuan",
                "attacker_troops_lost": 2000,
                "defender_troops_lost": 8000,
                "attacker_final_troops": 6000,
                "defender_final_troops": 12000,
                "new_owner": "han",
            }
            battle.apply_battle_result(conn, result)
            cursor = conn.execute("SELECT troops FROM generals WHERE id='caocao'")
            assert cursor.fetchone()[0] == 6000
            cursor = conn.execute("SELECT owner_faction_id FROM cities WHERE id='yingchuan'")
            assert cursor.fetchone()[0] == "han"
        finally:
            conn.close()

    def test_autonomy_finds_idle_generals(self, db_path):
        conn = sqlite3.connect(db_path)
        try:
            from autonomy import find_idle_generals
            generals = find_idle_generals(conn)
            ids = [g["id"] for g in generals]
            assert "xiahou" in ids
            assert "zhangjiao" in ids
            assert "caocao" not in ids
        finally:
            conn.close()

    def test_report_mode_persists(self, db_path):
        import battle
        conn = sqlite3.connect(db_path)
        try:
            assert battle.get_report_mode(conn) == "concise"
            battle.set_report_mode(conn, "detailed")
            assert battle.get_report_mode(conn) == "detailed"
        finally:
            conn.close()


class TestReflectFlow:
    """Test the memory reflection flow using agent_comm.reflect()."""

    def test_reflect_calls_invoke_for_each_general(self, tmp_path, monkeypatch):
        monkeypatch.setattr("agent_comm.HERMES_ROOT", str(tmp_path / ".hermes"))

        for gid in ["caocao", "liubei"]:
            p = tmp_path / ".hermes" / "profiles" / gid
            p.mkdir(parents=True)
            (p / "inbox.json").write_text("{}")

        call_count = [0]
        def fake_chat(*, system_prompt, user_message, model=None):
            call_count[0] += 1
            return '{"action": "reflect", "status": "ok"}'

        monkeypatch.setattr("agent_comm.llm_chat", fake_chat)
        from agent_comm import reflect
        results = reflect(["caocao", "liubei"], "a great battle occurred")
        assert len(results) == 2

    def test_reflect_writes_event_to_inbox(self, tmp_path, monkeypatch):
        monkeypatch.setattr("agent_comm.HERMES_ROOT", str(tmp_path / ".hermes"))

        def fake_chat(*, system_prompt, user_message, model=None):
            return "ok"

        monkeypatch.setattr("agent_comm.llm_chat", fake_chat)

        for gid in ["caocao"]:
            p = tmp_path / ".hermes" / "profiles" / gid
            p.mkdir(parents=True)
            (p / "inbox.json").write_text("{}")

        from agent_comm import reflect
        reflect(["caocao"], "battle at hulao pass")

        inbox = tmp_path / ".hermes" / "profiles" / "caocao" / "inbox.json"
        content = inbox.read_text()
        assert "battle at hulao pass" in content
        assert "memory_reflection" in content

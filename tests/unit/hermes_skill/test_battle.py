"""tests/unit/hermes_skill/test_battle.py"""

import json
import sqlite3

import pytest

from battle import (
    apply_battle_result,
    build_battle_context,
    format_battle_report,
    get_report_mode,
    identify_participants,
    set_report_mode,
)
from db import create_schema, insert_city, insert_faction, insert_general, upsert_state


@pytest.fixture
def conn(tmp_path):
    db = tmp_path / "test.db"
    c = sqlite3.connect(str(db))
    create_schema(c)
    insert_faction(c, "han", "汉室")
    insert_faction(c, "yellow", "黄巾")
    insert_city(c, "luoyang", "洛阳", 0, 0, "平原", "han")
    insert_city(c, "yingchuan", "颍川", 5, 3, "平原", "yellow")
    insert_general(
        c,
        {
            "id": "liubei",
            "name": "刘备",
            "war": 75,
            "cmd": 78,
            "intel": 68,
            "politics": 72,
            "charm": 92,
            "loyalty": 95,
            "troops": 8000,
            "food": 15,
            "position_city_id": "luoyang",
            "faction_id": "han",
            "is_player": False,
            "personality": json.dumps(
                {"temperament": "benevolent", "battle_style": "cautious", "risk_preference": "low"},
                ensure_ascii=False,
            ),
        },
    )
    insert_general(
        c,
        {
            "id": "guanyu",
            "name": "关羽",
            "war": 97,
            "cmd": 85,
            "intel": 75,
            "politics": 62,
            "charm": 88,
            "loyalty": 92,
            "troops": 5000,
            "food": 12,
            "position_city_id": "luoyang",
            "faction_id": "han",
            "is_player": False,
            "personality": json.dumps(
                {
                    "temperament": "proud",
                    "battle_style": "aggressive",
                    "risk_preference": "moderate",
                },
                ensure_ascii=False,
            ),
        },
    )
    insert_general(
        c,
        {
            "id": "zhangjiao",
            "name": "张角",
            "war": 40,
            "cmd": 70,
            "intel": 85,
            "politics": 60,
            "charm": 90,
            "loyalty": 100,
            "troops": 20000,
            "food": 20,
            "position_city_id": "yingchuan",
            "faction_id": "yellow",
            "is_player": False,
            "personality": json.dumps(
                {
                    "temperament": "fanatical",
                    "battle_style": "mass assault",
                    "risk_preference": "high",
                },
                ensure_ascii=False,
            ),
        },
    )
    upsert_state(c, "current_day", "15", 15)
    upsert_state(c, "season", "夏", 15)
    upsert_state(c, "weather", "雨", 15)
    c.commit()
    yield c
    c.close()


class TestIdentifyParticipants:
    def test_identifies_attacker_and_defender(self, conn):
        result = identify_participants(conn, "liubei", "zhangjiao")
        assert result["attacker"]["id"] == "liubei"
        assert result["defender"]["id"] == "zhangjiao"
        assert result["city"]["id"] == "yingchuan"
        assert result["terrain"] == "平原"
        assert result["season"] == "夏"
        assert result["weather"] == "雨"

    def test_finds_allies_in_same_city(self, conn):
        result = identify_participants(conn, "liubei", "zhangjiao")
        ally_ids = [a["id"] for a in result["attacker_allies"]]
        assert "guanyu" in ally_ids


class TestBuildBattleContext:
    def test_attacker_context_has_enemy_info(self, conn):
        participants = identify_participants(conn, "liubei", "zhangjiao")
        ctx = build_battle_context(participants, "attacker", "liubei")
        parsed = json.loads(ctx)
        assert parsed["side"] == "attacker"
        assert parsed["your_forces"]["troops"] == 8000
        assert parsed["enemy_forces"]["general"] == "张角"
        assert parsed["objective"] == "capture_city"
        assert parsed["weather"] == "雨"
        assert parsed["terrain"] == "平原"

    def test_defender_context_has_objective_hold(self, conn):
        participants = identify_participants(conn, "liubei", "zhangjiao")
        ctx = build_battle_context(participants, "defender", "zhangjiao")
        parsed = json.loads(ctx)
        assert parsed["side"] == "defender"
        assert parsed["objective"] == "hold_city"


class TestApplyBattleResult:
    def test_updates_troops(self, conn):
        result = {
            "outcome": "attacker_win",
            "attacker_id": "liubei",
            "defender_id": "zhangjiao",
            "city_id": "yingchuan",
            "attacker_troops_lost": 1200,
            "defender_troops_lost": 5000,
            "attacker_final_troops": 6800,
            "defender_final_troops": 15000,
            "new_owner": "han",
        }
        apply_battle_result(conn, result)
        cursor = conn.execute("SELECT troops FROM generals WHERE id='liubei'")
        assert cursor.fetchone()[0] == 6800
        cursor = conn.execute("SELECT troops FROM generals WHERE id='zhangjiao'")
        assert cursor.fetchone()[0] == 15000

    def test_changes_city_owner(self, conn):
        result = {
            "outcome": "attacker_win",
            "attacker_id": "liubei",
            "defender_id": "zhangjiao",
            "city_id": "yingchuan",
            "attacker_troops_lost": 1200,
            "defender_troops_lost": 5000,
            "attacker_final_troops": 6800,
            "defender_final_troops": 15000,
            "new_owner": "han",
        }
        apply_battle_result(conn, result)
        cursor = conn.execute("SELECT owner_faction_id FROM cities WHERE id='yingchuan'")
        assert cursor.fetchone()[0] == "han"

    def test_logs_battle_event(self, conn):
        result = {
            "outcome": "draw",
            "attacker_id": "liubei",
            "defender_id": "zhangjiao",
            "city_id": "yingchuan",
            "attacker_troops_lost": 800,
            "defender_troops_lost": 1000,
            "attacker_final_troops": 7200,
            "defender_final_troops": 19000,
            "new_owner": None,
        }
        apply_battle_result(conn, result)
        cursor = conn.execute("SELECT count(*) FROM events_log WHERE event_type='battle'")
        assert cursor.fetchone()[0] == 1

    def test_draw_does_not_change_owner(self, conn):
        result = {
            "outcome": "draw",
            "attacker_id": "liubei",
            "defender_id": "zhangjiao",
            "city_id": "yingchuan",
            "attacker_troops_lost": 800,
            "defender_troops_lost": 1000,
            "attacker_final_troops": 7200,
            "defender_final_troops": 19000,
            "new_owner": None,
        }
        apply_battle_result(conn, result)
        cursor = conn.execute("SELECT owner_faction_id FROM cities WHERE id='yingchuan'")
        assert cursor.fetchone()[0] == "yellow"  # unchanged


class TestReportMode:
    def test_default_is_concise(self, conn):
        assert get_report_mode(conn) == "concise"

    def test_set_and_get(self, conn):
        set_report_mode(conn, "detailed")
        assert get_report_mode(conn) == "detailed"


class TestFormatReport:
    def test_concise_format(self):
        events = [
            {
                "event_type": "battle",
                "details_json": json.dumps(
                    {
                        "outcome": "attacker_win",
                        "attacker_name": "刘备",
                        "defender_name": "张角",
                        "city_name": "颍川",
                        "attacker_troops_lost": 1200,
                        "defender_troops_lost": 5000,
                        "weather": "雨",
                        "narrative_concise": "刘备击败张角，攻克颍川。",  # noqa: RUF001
                    }
                ),
            }
        ]
        report = format_battle_report(events, "concise")
        assert "刘备" in report
        assert "颍川" in report
        assert "1200" in report

    def test_detailed_format_uses_narrative(self):
        events = [
            {
                "event_type": "battle",
                "details_json": json.dumps(
                    {
                        "outcome": "attacker_win",
                        "attacker_name": "刘备",
                        "defender_name": "张角",
                        "city_name": "颍川",
                        "attacker_troops_lost": 1200,
                        "defender_troops_lost": 5000,
                        "weather": "雨",
                        "narrative_concise": "简洁版。",
                        "narrative_detailed": "刘备率军冒雨进攻颍川。关羽一马当先...",
                    }
                ),
            }
        ]
        report = format_battle_report(events, "detailed")
        assert "刘备" in report
        assert "关羽" in report


class TestIdentifyParticipantsError:
    def test_raises_on_missing_general(self, conn):
        with pytest.raises(ValueError, match="未找到"):
            identify_participants(conn, "nonexistent", "zhangjiao")

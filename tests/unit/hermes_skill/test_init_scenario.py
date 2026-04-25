"""tests/unit/hermes_skill/test_init_scenario.py"""

from __future__ import annotations

import pytest

from init_scenario import (
    ScenarioInitError,
    build_scenario_prompt,
    build_soul_content,
    validate_scenario,
)


def _valid_scenario():
    return {
        "scenario": "黄巾之乱",
        "player_identity": {"id": "caocao", "display_name": "曹操", "faction_id": "han"},
        "cities": [
            {"id": "luoyang", "name": "洛阳", "x": 0, "y": 0, "terrain": "平原", "owner": "han"},
            {"id": "yingchuan", "name": "颍川", "x": 5, "y": 3, "terrain": "平原", "owner": "han"},
            {
                "id": "julu", "name": "巨鹿", "x": 8, "y": 5,
                "terrain": "平原", "owner": "yellow_turban",
            },
        ],
        "connections": [
            {"from": "luoyang", "to": "yingchuan", "distance": 5},
            {"from": "yingchuan", "to": "julu", "distance": 4},
        ],
        "generals": [
            {"id": "caocao", "name": "曹操", "war": 72, "command": 86, "intel": 91,
             "politics": 88, "charm": 80, "loyalty": None,
             "troops": 8000, "food": 15, "position": "luoyang",
             "faction": "han", "is_player": True,
             "personality": {"temperament": "ambitious", "battle_style": "aggressive",
               "risk_preference": "high", "lord_attitude": "self-serving",
               "ally_attitude": "pragmatic", "enemy_attitude": "ruthless"}},
            {"id": "zhangjiao", "name": "张角", "war": 40, "command": 70, "intel": 85,
             "politics": 60, "charm": 90, "loyalty": 100,
             "troops": 20000, "food": 20, "position": "julu",
             "faction": "yellow_turban", "is_player": False,
             "personality": {"temperament": "fanatical", "battle_style": "mass assault",
               "risk_preference": "high", "lord_attitude": "charismatic",
               "ally_attitude": "distrustful", "enemy_attitude": "contemptuous"}},
            {"id": "liubei", "name": "刘备", "war": 75, "command": 78, "intel": 68,
             "politics": 72, "charm": 92, "loyalty": 90,
             "troops": 5000, "food": 12, "position": "luoyang",
             "faction": "han", "is_player": False,
             "personality": {"temperament": "benevolent", "battle_style": "cautious",
               "risk_preference": "low", "lord_attitude": "loyal",
               "ally_attitude": "trusting", "enemy_attitude": "forgiving"}},
            {"id": "guanyu", "name": "关羽", "war": 97, "command": 85, "intel": 75,
             "politics": 62, "charm": 88, "loyalty": 95,
             "troops": 6000, "food": 12, "position": "luoyang",
             "faction": "han", "is_player": False,
             "personality": {"temperament": "proud", "battle_style": "duel-focused",
               "risk_preference": "moderate", "lord_attitude": "loyal",
               "ally_attitude": "respectful", "enemy_attitude": "arrogant"}},
            {"id": "zhangfei", "name": "张飞", "war": 98, "command": 70, "intel": 45,
             "politics": 30, "charm": 50, "loyalty": 92,
             "troops": 5000, "food": 12, "position": "luoyang",
             "faction": "han", "is_player": False,
             "personality": {"temperament": "impulsive", "battle_style": "charge",
               "risk_preference": "very high", "lord_attitude": "devoted",
               "ally_attitude": "brotherly", "enemy_attitude": "fierce"}},
        ],
        "relationships": [],
        "initial_state": {"day": 1, "season": "春", "weather": "晴"},
    }


class TestValidateScenario:
    def test_valid_scenario_passes(self):
        validate_scenario(_valid_scenario())  # should not raise

    def test_raises_when_insufficient_cities(self):
        data = _valid_scenario()
        data["cities"] = data["cities"][:2]
        with pytest.raises(ScenarioInitError, match="至少 3 座城池"):
            validate_scenario(data)

    def test_raises_when_insufficient_generals(self):
        data = _valid_scenario()
        data["generals"] = data["generals"][:4]
        with pytest.raises(ScenarioInitError, match="至少 5 名武将"):
            validate_scenario(data)

    def test_raises_when_no_player_general(self):
        data = _valid_scenario()
        for g in data["generals"]:
            g["is_player"] = False
        with pytest.raises(ScenarioInitError, match="is_player"):
            validate_scenario(data)

    def test_raises_when_player_has_loyalty(self):
        data = _valid_scenario()
        for g in data["generals"]:
            if g["is_player"]:
                g["loyalty"] = 100
        with pytest.raises(ScenarioInitError, match="loyalty"):
            validate_scenario(data)

    def test_raises_when_position_refers_to_missing_city(self):
        data = _valid_scenario()
        data["generals"][1]["position"] = "nonexistent"
        with pytest.raises(ScenarioInitError, match="position"):
            validate_scenario(data)

    def test_raises_when_connection_refers_to_missing_city(self):
        data = _valid_scenario()
        data["connections"][0]["from"] = "nonexistent"
        with pytest.raises(ScenarioInitError, match="connection"):
            validate_scenario(data)

    def test_raises_when_stat_out_of_range(self):
        data = _valid_scenario()
        data["generals"][0]["war"] = 999
        with pytest.raises(ScenarioInitError, match="war"):
            validate_scenario(data)

    def test_raises_when_troops_out_of_range(self):
        data = _valid_scenario()
        data["generals"][0]["troops"] = 50
        with pytest.raises(ScenarioInitError, match="troops"):
            validate_scenario(data)


class TestBuildPrompt:
    def test_renders_theme_and_player(self):
        prompt = build_scenario_prompt(theme="赤壁之战", player_name="周瑜")
        assert "赤壁之战" in prompt
        assert "周瑜" in prompt

    def test_contains_json_structure_reminder(self):
        prompt = build_scenario_prompt(theme="test", player_name="test")
        assert "cities" in prompt
        assert "generals" in prompt


class TestBuildSoulContent:
    def test_renders_all_fields(self):
        general = _valid_scenario()["generals"][0]
        content = build_soul_content(general, "汉室")
        assert "曹操" in content
        assert "ambitious" in content
        assert "武：72" in content  # noqa: RUF001
        assert "忠：—" in content  # noqa: RUF001

    def test_shows_loyalty_for_ai(self):
        general = _valid_scenario()["generals"][1]
        content = build_soul_content(general, "黄巾")
        assert "张角" in content
        assert "忠：100" in content  # noqa: RUF001

import pytest

from ai_war_game.domain.errors import ScenarioInvalidError
from ai_war_game.infrastructure.hermes.parser import parse_scenario_payload


def test_should_parse_valid_payload():
    scenario = parse_scenario_payload("赤壁前夜", _build_payload())

    assert scenario.theme == "赤壁前夜"
    assert scenario.summary == "刘备率军加入赤壁联盟。"
    assert scenario.starting_day == 3
    assert scenario.raw_payload == _build_payload()


def test_should_raise_when_summary_is_missing():
    payload = _build_payload()
    del payload["summary"]

    with pytest.raises(ScenarioInvalidError):
        parse_scenario_payload("赤壁前夜", payload)


def test_should_raise_when_factions_is_empty():
    payload = _build_payload()
    payload["factions"] = []

    with pytest.raises(ScenarioInvalidError):
        parse_scenario_payload("赤壁前夜", payload)


def test_should_raise_when_player_settlement_is_not_in_settlements():
    payload = _build_payload()
    payload["player_settlement_id"] = "unknown"

    with pytest.raises(ScenarioInvalidError):
        parse_scenario_payload("赤壁前夜", payload)


def _build_payload() -> dict:
    return {
        "summary": "刘备率军加入赤壁联盟。",
        "starting_day": 3,
        "player": {
            "display_name": "刘备",
            "faction_id": "shu",
        },
        "factions": [
            {
                "faction_id": "shu",
                "name": "蜀汉",
                "leader_character_id": "liubei",
            }
        ],
        "characters": [
            {
                "character_id": "liubei",
                "name": "刘备",
                "faction_id": "shu",
            }
        ],
        "settlements": [
            {
                "settlement_id": "jiangling",
                "name": "江陵",
                "controlling_faction_id": "shu",
            }
        ],
        "player_settlement_id": "jiangling",
    }

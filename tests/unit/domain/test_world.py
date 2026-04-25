import pytest

from ai_war_game.domain.world import Character, Faction, Settlement, WorldState


def test_should_build_world_state_with_minimal_fields():
    factions = (Faction(faction_id="shu", name="蜀汉", leader_character_id="liubei"),)
    characters = (Character(character_id="liubei", name="刘备", faction_id="shu"),)
    settlements = (Settlement(settlement_id="chengdu", name="成都", controlling_faction_id="shu"),)
    world = WorldState(
        current_day=1,
        factions=factions,
        characters=characters,
        settlements=settlements,
        player_settlement_id="chengdu",
    )
    assert world.current_day == 1
    assert world.faction("shu").name == "蜀汉"
    assert world.character("liubei").faction_id == "shu"
    assert world.settlement("chengdu").controlling_faction_id == "shu"


def test_should_advance_day():
    factions = (Faction(faction_id="shu", name="蜀汉", leader_character_id="liubei"),)
    characters = (Character(character_id="liubei", name="刘备", faction_id="shu"),)
    settlements = (Settlement(settlement_id="chengdu", name="成都", controlling_faction_id="shu"),)
    world = WorldState(
        current_day=1,
        factions=factions,
        characters=characters,
        settlements=settlements,
        player_settlement_id="chengdu",
    )
    advanced = world.advance_day()
    assert advanced.current_day == 2
    assert world.current_day == 1, "原对象不应被修改"


def test_should_reject_unknown_player_settlement():
    factions = (Faction(faction_id="shu", name="蜀汉", leader_character_id="liubei"),)
    characters = (Character(character_id="liubei", name="刘备", faction_id="shu"),)
    settlements = (Settlement(settlement_id="chengdu", name="成都", controlling_faction_id="shu"),)
    with pytest.raises(ValueError, match="player_settlement_id"):
        WorldState(
            current_day=1,
            factions=factions,
            characters=characters,
            settlements=settlements,
            player_settlement_id="luoyang",
        )


def test_should_reject_non_positive_day():
    with pytest.raises(ValueError, match="current_day"):
        WorldState(
            current_day=0,
            factions=(Faction(faction_id="shu", name="蜀汉", leader_character_id="liubei"),),
            characters=(Character(character_id="liubei", name="刘备", faction_id="shu"),),
            settlements=(
                Settlement(
                    settlement_id="chengdu",
                    name="成都",
                    controlling_faction_id="shu",
                ),
            ),
            player_settlement_id="chengdu",
        )

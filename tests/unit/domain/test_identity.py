import pytest

from ai_war_game.domain.identity import PlayerIdentity


def test_should_construct_player_identity():
    identity = PlayerIdentity(player_id="p1", display_name="刘备", faction_id="shu")
    assert identity.player_id == "p1"
    assert identity.display_name == "刘备"
    assert identity.faction_id == "shu"


def test_should_reject_blank_player_id():
    with pytest.raises(ValueError, match="player_id"):
        PlayerIdentity(player_id="", display_name="刘备", faction_id="shu")


def test_should_reject_blank_display_name():
    with pytest.raises(ValueError, match="display_name"):
        PlayerIdentity(player_id="p1", display_name="   ", faction_id="shu")


def test_should_be_frozen():
    identity = PlayerIdentity(player_id="p1", display_name="刘备", faction_id="shu")
    with pytest.raises(AttributeError):
        identity.player_id = "p2"  # type: ignore[misc]

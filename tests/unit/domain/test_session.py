from datetime import UTC, datetime

import pytest

from ai_war_game.domain.command import CommandRequest
from ai_war_game.domain.identity import PlayerIdentity
from ai_war_game.domain.scenario import Scenario
from ai_war_game.domain.session import GameSession
from ai_war_game.domain.world import Character, Faction, Settlement, WorldState


def _build_session() -> GameSession:
    return GameSession(
        save_id="save-1",
        created_at=datetime(2026, 4, 25, tzinfo=UTC),
        updated_at=datetime(2026, 4, 25, tzinfo=UTC),
        player=PlayerIdentity(player_id="p1", display_name="刘备", faction_id="shu"),
        scenario=Scenario(
            theme="三国",
            summary="群雄逐鹿",
            starting_day=1,
            raw_payload={},
        ),
        world=WorldState(
            current_day=1,
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
        ),
    )


def test_should_apply_player_command_and_advance_day():
    session = _build_session()
    request = CommandRequest(
        save_id="save-1",
        player_id="p1",
        text="进军洛阳",
        issued_at=datetime(2026, 4, 25, 12, 0, tzinfo=UTC),
    )
    new_session, event, result = session.apply_player_command(request)

    assert result.accepted is True
    assert result.new_day == 2
    assert new_session.world.current_day == 2
    assert new_session.updated_at == request.issued_at
    assert event.kind == "player_action_logged"
    assert event.day == 2
    assert event.payload["text"] == "进军洛阳"


def test_should_reject_command_for_other_save():
    session = _build_session()
    request = CommandRequest(
        save_id="other",
        player_id="p1",
        text="x",
        issued_at=datetime(2026, 4, 25, tzinfo=UTC),
    )
    with pytest.raises(ValueError, match="save_id"):
        session.apply_player_command(request)


def test_should_reject_command_for_other_player():
    session = _build_session()
    request = CommandRequest(
        save_id="save-1",
        player_id="p2",
        text="x",
        issued_at=datetime(2026, 4, 25, tzinfo=UTC),
    )
    with pytest.raises(ValueError, match="player_id"):
        session.apply_player_command(request)

from datetime import UTC, datetime

import pytest

from ai_war_game.domain.errors import SaveCorruptedError
from ai_war_game.domain.events import GameEvent
from ai_war_game.domain.identity import PlayerIdentity
from ai_war_game.domain.scenario import Scenario
from ai_war_game.domain.session import GameSession
from ai_war_game.domain.world import Character, Faction, Settlement, WorldState
from ai_war_game.infrastructure.persistence.codecs import (
    decode_event,
    decode_session,
    decode_world,
    encode_event,
    encode_session,
    encode_world,
)


def test_should_round_trip_world():
    world = _build_world()

    restored = decode_world(encode_world(world))

    assert restored == world


def test_should_round_trip_session():
    session = _build_session()

    restored = decode_session(encode_session(session))

    assert restored == session


def test_should_raise_when_schema_version_is_unsupported():
    payload = encode_session(_build_session())
    payload["schema_version"] = 999

    with pytest.raises(SaveCorruptedError):
        decode_session(payload)


def test_should_round_trip_event():
    event = GameEvent(
        event_id="evt-1",
        kind="player_action_logged",
        day=2,
        occurred_at=datetime(2026, 4, 25, 12, 0, tzinfo=UTC),
        payload={"text": "进军"},
    )

    restored = decode_event(encode_event(event))

    assert restored == event


def _build_session() -> GameSession:
    now = datetime(2026, 4, 25, 12, 0, tzinfo=UTC)
    return GameSession(
        save_id="save-1",
        created_at=now,
        updated_at=now,
        player=PlayerIdentity(
            player_id="player-1",
            display_name="刘备",
            faction_id="shu",
        ),
        scenario=Scenario(
            theme="赤壁前夜",
            summary="刘备加入赤壁战局。",
            starting_day=1,
            raw_payload={"seed": "demo"},
        ),
        world=_build_world(),
    )


def _build_world() -> WorldState:
    return WorldState(
        current_day=1,
        factions=(
            Faction(
                faction_id="shu",
                name="蜀汉",
                leader_character_id="liubei",
            ),
        ),
        characters=(
            Character(
                character_id="liubei",
                name="刘备",
                faction_id="shu",
            ),
        ),
        settlements=(
            Settlement(
                settlement_id="chengdu",
                name="成都",
                controlling_faction_id="shu",
            ),
        ),
        player_settlement_id="chengdu",
    )

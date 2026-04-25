import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from ai_war_game.domain.errors import SaveCorruptedError, SaveNotFoundError
from ai_war_game.domain.events import GameEvent
from ai_war_game.domain.identity import PlayerIdentity
from ai_war_game.domain.scenario import Scenario
from ai_war_game.domain.session import GameSession
from ai_war_game.domain.world import Character, Faction, Settlement, WorldState
from ai_war_game.infrastructure.persistence.file_repository import FileGameRepository
from ai_war_game.infrastructure.persistence.paths import SaveLocator


def test_should_round_trip_session_and_write_sidecar_files(save_root: Path):
    repository = FileGameRepository(locator=SaveLocator(root=save_root))
    session = _build_session(save_id="save-1")

    repository.save_session(session)

    restored = repository.load_session("save-1")

    assert restored == session
    assert (save_root / "save-1" / "scenario.json").exists()
    assert json.loads((save_root / "save-1" / "scenario.json").read_text(encoding="utf-8")) == {
        "theme": "赤壁前夜",
        "summary": "刘备加入赤壁战局。",
        "starting_day": 1,
        "raw_payload": {"seed": "demo"},
    }


def test_should_append_events_in_order(save_root: Path):
    repository = FileGameRepository(locator=SaveLocator(root=save_root))
    repository.save_session(_build_session(save_id="save-1"))
    first_event = _build_event(event_id="evt-1", day=1, text="征兵")
    second_event = _build_event(event_id="evt-2", day=2, text="出征")

    repository.append_event("save-1", first_event)
    repository.append_event("save-1", second_event)

    assert repository.events("save-1") == [first_event, second_event]


def test_should_raise_when_loading_missing_save(save_root: Path):
    repository = FileGameRepository(locator=SaveLocator(root=save_root))

    with pytest.raises(SaveNotFoundError):
        repository.load_session("missing")


def test_should_raise_when_appending_event_to_missing_save(save_root: Path):
    repository = FileGameRepository(locator=SaveLocator(root=save_root))

    with pytest.raises(SaveNotFoundError):
        repository.append_event("missing", _build_event(event_id="evt-1", day=1, text="征兵"))


def test_should_raise_when_session_json_is_invalid(save_root: Path):
    save_dir = save_root / "save-1"
    save_dir.mkdir()
    (save_dir / "session.json").write_text("{bad json", encoding="utf-8")
    repository = FileGameRepository(locator=SaveLocator(root=save_root))

    with pytest.raises(SaveCorruptedError):
        repository.load_session("save-1")


def test_should_raise_when_event_line_is_invalid_json(save_root: Path):
    save_dir = save_root / "save-1"
    save_dir.mkdir()
    (save_dir / "events.jsonl").write_text("{bad json\n", encoding="utf-8")
    repository = FileGameRepository(locator=SaveLocator(root=save_root))

    with pytest.raises(SaveCorruptedError):
        repository.events("save-1")


def test_should_list_save_ids_in_sorted_order(save_root: Path):
    repository = FileGameRepository(locator=SaveLocator(root=save_root))
    repository.save_session(_build_session(save_id="save-b"))
    repository.save_session(_build_session(save_id="save-a"))

    assert repository.list_save_ids() == ["save-a", "save-b"]


def _build_session(save_id: str) -> GameSession:
    now = datetime(2026, 4, 25, 12, 0, tzinfo=UTC)
    return GameSession(
        save_id=save_id,
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
        world=WorldState(
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
        ),
    )


def _build_event(event_id: str, day: int, text: str) -> GameEvent:
    return GameEvent(
        event_id=event_id,
        kind="player_action_logged",
        day=day,
        occurred_at=datetime(2026, 4, 25, 12, day, tzinfo=UTC),
        payload={"text": text},
    )

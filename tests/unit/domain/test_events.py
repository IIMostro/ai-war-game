from datetime import UTC, datetime

import pytest

from ai_war_game.domain.events import GameEvent


def test_should_build_event():
    event = GameEvent(
        event_id="evt-1",
        kind="player_action_logged",
        day=1,
        occurred_at=datetime(2026, 4, 25, tzinfo=UTC),
        payload={"text": "进军洛阳"},
    )
    assert event.kind == "player_action_logged"
    assert event.payload["text"] == "进军洛阳"


def test_should_reject_blank_event_id():
    with pytest.raises(ValueError, match="event_id"):
        GameEvent(
            event_id="",
            kind="x",
            day=1,
            occurred_at=datetime.now(UTC),
            payload={},
        )

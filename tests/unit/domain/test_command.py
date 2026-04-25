from datetime import UTC, datetime

import pytest

from ai_war_game.domain.command import CommandRequest, CommandResult


def test_should_build_command_request():
    req = CommandRequest(
        save_id="save-1",
        player_id="p1",
        text="进军洛阳",
        issued_at=datetime(2026, 4, 25, tzinfo=UTC),
    )
    assert req.save_id == "save-1"
    assert req.text == "进军洛阳"


def test_should_reject_blank_text():
    with pytest.raises(ValueError, match="text"):
        CommandRequest(save_id="s", player_id="p", text="   ", issued_at=datetime.now(UTC))


def test_should_build_command_result():
    res = CommandResult(
        save_id="save-1",
        accepted=True,
        message="已记录",
        new_day=2,
    )
    assert res.accepted is True
    assert res.new_day == 2

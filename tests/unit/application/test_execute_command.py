from datetime import UTC, datetime

import pytest

from ai_war_game.application.create_game import CreateGameService
from ai_war_game.application.dto import CreateGameInput
from ai_war_game.application.execute_command import ExecuteCommandService
from ai_war_game.domain.command import CommandRequest
from ai_war_game.domain.errors import SaveNotFoundError


def test_should_execute_command_advance_day_and_store_event(
    fake_hermes_ok,
    fake_scenario_generator,
    in_memory_repo,
    now_utc,
):
    CreateGameService(
        hermes_health=fake_hermes_ok,
        scenario_generator=fake_scenario_generator,
        repository=in_memory_repo,
    ).execute(
        CreateGameInput(
            save_id="save-1",
            theme="赤壁前夜",
            player_id="p1",
            player_display_name="刘备",
            issued_at=now_utc,
        )
    )
    command_service = ExecuteCommandService(repository=in_memory_repo)

    result = command_service.execute(
        CommandRequest(
            save_id="save-1",
            player_id="p1",
            text="进军洛阳",
            issued_at=datetime(2026, 4, 26, 9, 0, tzinfo=UTC),
        )
    )
    session = in_memory_repo.load_session("save-1")
    events = in_memory_repo.events("save-1")

    assert result.new_day == 2
    assert session.world.current_day == 2
    assert len(events) == 1
    assert events[0].kind == "player_action_logged"


def test_should_raise_when_executing_command_for_missing_save(in_memory_repo, now_utc):
    command_service = ExecuteCommandService(repository=in_memory_repo)

    with pytest.raises(SaveNotFoundError):
        command_service.execute(
            CommandRequest(
                save_id="missing",
                player_id="p1",
                text="进军洛阳",
                issued_at=now_utc,
            )
        )

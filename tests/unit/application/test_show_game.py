import pytest

from ai_war_game.application.create_game import CreateGameService
from ai_war_game.application.dto import CreateGameInput
from ai_war_game.application.show_game import ShowGameService
from ai_war_game.domain.errors import SaveNotFoundError


def test_should_show_seeded_game_state(
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
    show_service = ShowGameService(repository=in_memory_repo)

    result = show_service.execute(save_id="save-1")

    assert result.save_id == "save-1"
    assert result.current_day == 1
    assert result.player_display_name == "刘备"
    assert result.faction_name == "蜀汉"
    assert result.summary == "刘备 加入 赤壁前夜 战局。"
    assert result.recent_events == ()


def test_should_raise_when_showing_missing_save(in_memory_repo):
    show_service = ShowGameService(repository=in_memory_repo)

    with pytest.raises(SaveNotFoundError):
        show_service.execute(save_id="missing")

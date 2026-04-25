from ai_war_game.application.create_game import CreateGameService
from ai_war_game.application.dto import CreateGameInput
from ai_war_game.application.list_saves import ListSavesService


def test_should_return_empty_list_for_empty_repository(in_memory_repo):
    result = ListSavesService(repository=in_memory_repo).execute()

    assert result == []


def test_should_list_saves_sorted_by_save_id(
    fake_hermes_ok,
    fake_scenario_generator,
    in_memory_repo,
    now_utc,
):
    create_service = CreateGameService(
        hermes_health=fake_hermes_ok,
        scenario_generator=fake_scenario_generator,
        repository=in_memory_repo,
    )
    create_service.execute(
        CreateGameInput(
            save_id="save-b",
            theme="官渡之前",
            player_id="p1",
            player_display_name="刘备",
            issued_at=now_utc,
        )
    )
    create_service.execute(
        CreateGameInput(
            save_id="save-a",
            theme="赤壁前夜",
            player_id="p1",
            player_display_name="刘备",
            issued_at=now_utc,
        )
    )

    result = ListSavesService(repository=in_memory_repo).execute()

    assert [item.save_id for item in result] == ["save-a", "save-b"]

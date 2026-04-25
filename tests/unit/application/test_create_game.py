from ai_war_game.application.create_game import CreateGameService
from ai_war_game.application.dto import CreateGameInput
from ai_war_game.domain.errors import HermesUnavailableError


def test_should_fail_fast_without_creating_session(
    fake_hermes_failing,
    fake_scenario_generator,
    in_memory_repo,
    now_utc,
):
    service = CreateGameService(
        hermes_health=fake_hermes_failing,
        scenario_generator=fake_scenario_generator,
        repository=in_memory_repo,
    )
    request = CreateGameInput(
        save_id="save-2",
        theme="赤壁前夜",
        player_id="p1",
        player_display_name="刘备",
        issued_at=now_utc,
    )

    try:
        service.execute(request)
    except HermesUnavailableError:
        pass
    else:
        raise AssertionError("应抛出 HermesUnavailableError")

    assert in_memory_repo.list_save_ids() == []


def test_should_create_session_with_request_timestamp(
    fake_hermes_ok,
    fake_scenario_generator,
    in_memory_repo,
    now_utc,
):
    service = CreateGameService(
        hermes_health=fake_hermes_ok,
        scenario_generator=fake_scenario_generator,
        repository=in_memory_repo,
    )
    request = CreateGameInput(
        save_id="save-1",
        theme="赤壁前夜",
        player_id="p1",
        player_display_name="刘备",
        issued_at=now_utc,
    )

    result = service.execute(request)
    session = in_memory_repo.load_session("save-1")

    assert result.save_id == "save-1"
    assert result.starting_day == 1
    assert result.summary == "刘备 加入 赤壁前夜 战局。"
    assert session.created_at == now_utc
    assert session.updated_at == now_utc

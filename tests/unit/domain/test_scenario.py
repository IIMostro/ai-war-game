import pytest

from ai_war_game.domain.scenario import Scenario


def test_should_build_scenario():
    scenario = Scenario(
        theme="三国演义",
        summary="群雄逐鹿，蜀汉初立。",  # noqa: RUF001
        starting_day=1,
        raw_payload={"theme": "三国演义"},
    )
    assert scenario.theme == "三国演义"
    assert scenario.starting_day == 1
    assert scenario.raw_payload["theme"] == "三国演义"


def test_should_reject_blank_theme():
    with pytest.raises(ValueError, match="theme"):
        Scenario(theme="", summary="...", starting_day=1, raw_payload={})


def test_should_reject_blank_summary():
    with pytest.raises(ValueError, match="summary"):
        Scenario(theme="三国", summary="   ", starting_day=1, raw_payload={})


def test_should_reject_non_positive_starting_day():
    with pytest.raises(ValueError, match="starting_day"):
        Scenario(theme="三国", summary="...", starting_day=0, raw_payload={})

import pytest

from ai_war_game.domain.errors import ScenarioGenerationError, ScenarioInvalidError
from ai_war_game.infrastructure.hermes.client import (
    HermesScenarioGenerator,
    SubprocessOutcome,
)


def test_should_generate_scenario_from_successful_runner():
    captured: dict[str, object] = {}

    def runner(*, argv: list[str], stdin: str, timeout: float) -> SubprocessOutcome:
        captured["argv"] = argv
        captured["stdin"] = stdin
        captured["timeout"] = timeout
        return SubprocessOutcome(
            returncode=0,
            stdout=_valid_stdout(),
            stderr="",
        )

    generator = HermesScenarioGenerator(
        bin_path="hermes",
        model="hermes-3",
        config_path="/tmp/hermes.yaml",
        runner=runner,
        timeout_seconds=45.0,
    )

    scenario = generator.generate(theme="赤壁前夜", player_display_name="刘备")

    assert scenario.theme == "赤壁前夜"
    assert scenario.summary == "刘备率军加入赤壁联盟。"
    assert scenario.starting_day == 2
    assert captured["argv"] == [
        "hermes",
        "skill",
        "run",
        "scenario-generator",
        "--model",
        "hermes-3",
        "--config",
        "/tmp/hermes.yaml",
    ]
    assert "主题: 赤壁前夜" in str(captured["stdin"])
    assert captured["timeout"] == 45.0


def test_should_raise_when_runner_returns_non_zero():
    def runner(*, argv: list[str], stdin: str, timeout: float) -> SubprocessOutcome:
        return SubprocessOutcome(returncode=7, stdout="", stderr="boom")

    generator = HermesScenarioGenerator(
        bin_path="hermes",
        model="hermes-3",
        config_path="/tmp/hermes.yaml",
        runner=runner,
    )

    with pytest.raises(ScenarioGenerationError, match="boom"):
        generator.generate(theme="赤壁前夜", player_display_name="刘备")


def test_should_raise_when_stdout_is_not_json():
    def runner(*, argv: list[str], stdin: str, timeout: float) -> SubprocessOutcome:
        return SubprocessOutcome(returncode=0, stdout="not-json", stderr="")

    generator = HermesScenarioGenerator(
        bin_path="hermes",
        model="hermes-3",
        config_path="/tmp/hermes.yaml",
        runner=runner,
    )

    with pytest.raises(ScenarioGenerationError, match="不是合法 JSON"):
        generator.generate(theme="赤壁前夜", player_display_name="刘备")


def test_should_propagate_invalid_payload_error():
    def runner(*, argv: list[str], stdin: str, timeout: float) -> SubprocessOutcome:
        return SubprocessOutcome(
            returncode=0,
            stdout=(
                '{"starting_day": 1, "player": {}, "factions": [], '
                '"characters": [], "settlements": [], '
                '"player_settlement_id": "x"}'
            ),
            stderr="",
        )

    generator = HermesScenarioGenerator(
        bin_path="hermes",
        model="hermes-3",
        config_path="/tmp/hermes.yaml",
        runner=runner,
    )

    with pytest.raises(ScenarioInvalidError):
        generator.generate(theme="赤壁前夜", player_display_name="刘备")


def _valid_stdout() -> str:
    return """
{
  "summary": "刘备率军加入赤壁联盟。",
  "starting_day": 2,
  "player": {
    "display_name": "刘备",
    "faction_id": "shu"
  },
  "factions": [
    {
      "faction_id": "shu",
      "name": "蜀汉",
      "leader_character_id": "liubei"
    }
  ],
  "characters": [
    {
      "character_id": "liubei",
      "name": "刘备",
      "faction_id": "shu"
    }
  ],
  "settlements": [
    {
      "settlement_id": "jiangling",
      "name": "江陵",
      "controlling_faction_id": "shu"
    }
  ],
  "player_settlement_id": "jiangling"
}
""".strip()

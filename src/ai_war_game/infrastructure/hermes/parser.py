"""Hermes 输出解析与最小结构校验."""

from typing import Any

from ai_war_game.domain.errors import ScenarioInvalidError
from ai_war_game.domain.scenario import Scenario

REQUIRED_TOP_KEYS = (
    "summary",
    "starting_day",
    "player",
    "factions",
    "characters",
    "settlements",
    "player_settlement_id",
)
REQUIRED_PLAYER_KEYS = ("display_name", "faction_id")
REQUIRED_FACTION_KEYS = ("faction_id", "name", "leader_character_id")
REQUIRED_CHARACTER_KEYS = ("character_id", "name", "faction_id")
REQUIRED_SETTLEMENT_KEYS = ("settlement_id", "name", "controlling_faction_id")


def parse_scenario_payload(theme: str, payload: dict[str, Any]) -> Scenario:
    _ensure_keys(payload, REQUIRED_TOP_KEYS, "scenario")
    _ensure_keys(payload["player"], REQUIRED_PLAYER_KEYS, "scenario.player")

    _ensure_non_empty_list(payload["factions"], "scenario.factions")
    for index, item in enumerate(payload["factions"]):
        _ensure_keys(item, REQUIRED_FACTION_KEYS, f"scenario.factions[{index}]")

    _ensure_non_empty_list(payload["characters"], "scenario.characters")
    for index, item in enumerate(payload["characters"]):
        _ensure_keys(item, REQUIRED_CHARACTER_KEYS, f"scenario.characters[{index}]")

    _ensure_non_empty_list(payload["settlements"], "scenario.settlements")
    settlement_ids: set[str] = set()
    for index, item in enumerate(payload["settlements"]):
        _ensure_keys(item, REQUIRED_SETTLEMENT_KEYS, f"scenario.settlements[{index}]")
        settlement_ids.add(item["settlement_id"])

    if payload["player_settlement_id"] not in settlement_ids:
        raise ScenarioInvalidError(
            f"player_settlement_id={payload['player_settlement_id']} 不在 settlements 中"
        )

    starting_day = int(payload["starting_day"])
    if starting_day < 1:
        raise ScenarioInvalidError("starting_day 必须 >= 1")

    summary = str(payload["summary"]).strip()
    if not summary:
        raise ScenarioInvalidError("summary 不能为空")

    return Scenario(
        theme=theme,
        summary=summary,
        starting_day=starting_day,
        raw_payload=payload,
    )


def _ensure_keys(obj: Any, keys: tuple[str, ...], path: str) -> None:
    if not isinstance(obj, dict):
        raise ScenarioInvalidError(f"{path} 必须是对象")
    for key in keys:
        if key not in obj:
            raise ScenarioInvalidError(f"{path}.{key} 缺失")


def _ensure_non_empty_list(obj: Any, path: str) -> None:
    if not isinstance(obj, list) or not obj:
        raise ScenarioInvalidError(f"{path} 必须是非空数组")

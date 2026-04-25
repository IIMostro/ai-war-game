"""领域对象 <-> JSON 字典编解码."""

from datetime import datetime
from typing import Any

from ai_war_game.domain.errors import SaveCorruptedError
from ai_war_game.domain.events import GameEvent
from ai_war_game.domain.identity import PlayerIdentity
from ai_war_game.domain.scenario import Scenario
from ai_war_game.domain.session import SCHEMA_VERSION, GameSession
from ai_war_game.domain.world import Character, Faction, Settlement, WorldState


def encode_world(world: WorldState) -> dict[str, Any]:
    return {
        "current_day": world.current_day,
        "factions": [
            {
                "faction_id": faction.faction_id,
                "name": faction.name,
                "leader_character_id": faction.leader_character_id,
            }
            for faction in world.factions
        ],
        "characters": [
            {
                "character_id": character.character_id,
                "name": character.name,
                "faction_id": character.faction_id,
            }
            for character in world.characters
        ],
        "settlements": [
            {
                "settlement_id": settlement.settlement_id,
                "name": settlement.name,
                "controlling_faction_id": settlement.controlling_faction_id,
            }
            for settlement in world.settlements
        ],
        "player_settlement_id": world.player_settlement_id,
    }


def decode_world(payload: dict[str, Any]) -> WorldState:
    return WorldState(
        current_day=int(payload["current_day"]),
        factions=tuple(Faction(**faction) for faction in payload["factions"]),
        characters=tuple(Character(**character) for character in payload["characters"]),
        settlements=tuple(Settlement(**settlement) for settlement in payload["settlements"]),
        player_settlement_id=payload["player_settlement_id"],
    )


def encode_session(session: GameSession) -> dict[str, Any]:
    return {
        "schema_version": session.schema_version,
        "save_id": session.save_id,
        "created_at": session.created_at.isoformat(),
        "updated_at": session.updated_at.isoformat(),
        "player": {
            "player_id": session.player.player_id,
            "display_name": session.player.display_name,
            "faction_id": session.player.faction_id,
        },
        "scenario": {
            "theme": session.scenario.theme,
            "summary": session.scenario.summary,
            "starting_day": session.scenario.starting_day,
            "raw_payload": session.scenario.raw_payload,
        },
        "world": encode_world(session.world),
    }


def decode_session(payload: dict[str, Any]) -> GameSession:
    version = payload.get("schema_version")
    if version != SCHEMA_VERSION:
        raise SaveCorruptedError(f"不支持的 schema_version={version} (期望 {SCHEMA_VERSION})")
    try:
        return GameSession(
            save_id=payload["save_id"],
            created_at=datetime.fromisoformat(payload["created_at"]),
            updated_at=datetime.fromisoformat(payload["updated_at"]),
            player=PlayerIdentity(**payload["player"]),
            scenario=Scenario(**payload["scenario"]),
            world=decode_world(payload["world"]),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise SaveCorruptedError(f"session 结构损坏: {exc}") from exc


def encode_event(event: GameEvent) -> dict[str, Any]:
    return {
        "event_id": event.event_id,
        "kind": event.kind,
        "day": event.day,
        "occurred_at": event.occurred_at.isoformat(),
        "payload": event.payload,
    }


def decode_event(payload: dict[str, Any]) -> GameEvent:
    try:
        return GameEvent(
            event_id=payload["event_id"],
            kind=payload["kind"],
            day=int(payload["day"]),
            occurred_at=datetime.fromisoformat(payload["occurred_at"]),
            payload=payload.get("payload", {}),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise SaveCorruptedError(f"event 结构损坏: {exc}") from exc

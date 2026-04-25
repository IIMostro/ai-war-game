"""创建新游戏的应用服务。"""

from ai_war_game.application.dto import CreateGameInput, CreateGameOutput
from ai_war_game.application.ports import GameRepository, HermesHealth, ScenarioGenerator
from ai_war_game.domain.errors import HermesUnavailableError
from ai_war_game.domain.identity import PlayerIdentity
from ai_war_game.domain.session import GameSession
from ai_war_game.domain.world import Character, Faction, Settlement, WorldState


class CreateGameService:
    def __init__(
        self,
        *,
        hermes_health: HermesHealth,
        scenario_generator: ScenarioGenerator,
        repository: GameRepository,
    ) -> None:
        self._hermes_health = hermes_health
        self._scenario_generator = scenario_generator
        self._repository = repository

    def execute(self, request: CreateGameInput) -> CreateGameOutput:
        if not self._hermes_health.check():
            raise HermesUnavailableError("Hermes health check failed")

        scenario = self._scenario_generator.generate(
            theme=request.theme,
            player_display_name=request.player_display_name,
        )
        player = PlayerIdentity(
            player_id=request.player_id,
            display_name=request.player_display_name,
            faction_id=str(scenario.raw_payload["player_faction_id"]),
        )
        world = WorldState(
            current_day=scenario.starting_day,
            factions=tuple(
                Faction(
                    faction_id=str(item["faction_id"]),
                    name=str(item["name"]),
                    leader_character_id=str(item["leader_character_id"]),
                )
                for item in scenario.raw_payload["factions"]
            ),
            characters=tuple(
                Character(
                    character_id=str(item["character_id"]),
                    name=str(item["name"]),
                    faction_id=str(item["faction_id"]),
                )
                for item in scenario.raw_payload["characters"]
            ),
            settlements=tuple(
                Settlement(
                    settlement_id=str(item["settlement_id"]),
                    name=str(item["name"]),
                    controlling_faction_id=str(item["controlling_faction_id"]),
                )
                for item in scenario.raw_payload["settlements"]
            ),
            player_settlement_id=str(scenario.raw_payload["player_settlement_id"]),
        )
        session = GameSession(
            save_id=request.save_id,
            created_at=request.issued_at,
            updated_at=request.issued_at,
            player=player,
            scenario=scenario,
            world=world,
        )
        self._repository.save_session(session)
        return CreateGameOutput(
            save_id=session.save_id,
            starting_day=session.world.current_day,
            summary=session.scenario.summary,
        )

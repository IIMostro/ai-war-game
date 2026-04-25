"""创建新游戏的应用服务。"""

from ai_war_game.application.dto import CreateGameInput, CreateGameOutput
from ai_war_game.application.ports import GameRepository, HermesHealth, ScenarioGenerator
from ai_war_game.domain.errors import ScenarioInvalidError
from ai_war_game.domain.identity import PlayerIdentity
from ai_war_game.domain.scenario import Scenario
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
        # 1. 环境检查; 失败时由 check 自身抛 HermesUnavailableError
        self._hermes_health.check()

        # 2. 调用 Hermes 生成剧本
        scenario = self._scenario_generator.generate(
            theme=request.theme,
            player_display_name=request.player_display_name,
        )

        # 3. 校验最小结构 + 构造 WorldState 与 PlayerIdentity
        world, player = _build_world_from_scenario(scenario, player_id=request.player_id)

        # 4. 构造会话并落盘
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


def _build_world_from_scenario(
    scenario: Scenario, *, player_id: str
) -> tuple[WorldState, PlayerIdentity]:
    payload = scenario.raw_payload
    try:
        player_meta = payload["player"]
        factions_data = payload["factions"]
        characters_data = payload["characters"]
        settlements_data = payload["settlements"]
        player_settlement_id = payload["player_settlement_id"]
    except KeyError as exc:
        raise ScenarioInvalidError(f"剧本缺少必填字段: {exc}") from exc

    if not factions_data or not characters_data or not settlements_data:
        raise ScenarioInvalidError("剧本至少需要 1 个势力/角色/聚落")

    factions = tuple(
        Faction(
            faction_id=str(item["faction_id"]),
            name=str(item["name"]),
            leader_character_id=str(item["leader_character_id"]),
        )
        for item in factions_data
    )
    characters = tuple(
        Character(
            character_id=str(item["character_id"]),
            name=str(item["name"]),
            faction_id=str(item["faction_id"]),
        )
        for item in characters_data
    )
    settlements = tuple(
        Settlement(
            settlement_id=str(item["settlement_id"]),
            name=str(item["name"]),
            controlling_faction_id=str(item["controlling_faction_id"]),
        )
        for item in settlements_data
    )
    world = WorldState(
        current_day=scenario.starting_day,
        factions=factions,
        characters=characters,
        settlements=settlements,
        player_settlement_id=str(player_settlement_id),
    )
    player = PlayerIdentity(
        player_id=player_id,
        display_name=str(player_meta["display_name"]),
        faction_id=str(player_meta["faction_id"]),
    )
    return world, player

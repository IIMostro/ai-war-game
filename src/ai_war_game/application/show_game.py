"""展示游戏状态的应用服务。"""

from ai_war_game.application.dto import ShowGameOutput
from ai_war_game.application.ports import GameRepository


class ShowGameService:
    def __init__(self, *, repository: GameRepository) -> None:
        self._repository = repository

    def execute(self, *, save_id: str) -> ShowGameOutput:
        session = self._repository.load_session(save_id)
        faction = session.world.faction(session.player.faction_id)
        recent_events = tuple(event.kind for event in self._repository.events(save_id))
        return ShowGameOutput(
            save_id=session.save_id,
            current_day=session.world.current_day,
            player_display_name=session.player.display_name,
            faction_name=faction.name,
            summary=session.scenario.summary,
            recent_events=recent_events,
        )

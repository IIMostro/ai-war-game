"""列出存档摘要的应用服务。"""

from ai_war_game.application.dto import SaveSummary
from ai_war_game.application.ports import GameRepository


class ListSavesService:
    def __init__(self, *, repository: GameRepository) -> None:
        self._repository = repository

    def execute(self) -> list[SaveSummary]:
        summaries: list[SaveSummary] = []
        for save_id in sorted(self._repository.list_save_ids()):
            session = self._repository.load_session(save_id)
            summaries.append(
                SaveSummary(
                    save_id=session.save_id,
                    created_at=session.created_at,
                    updated_at=session.updated_at,
                    current_day=session.world.current_day,
                    player_display_name=session.player.display_name,
                )
            )
        return summaries

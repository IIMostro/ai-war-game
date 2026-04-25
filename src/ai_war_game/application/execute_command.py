"""执行玩家命令的应用服务。"""

from ai_war_game.application.ports import GameRepository
from ai_war_game.domain.command import CommandRequest, CommandResult


class ExecuteCommandService:
    def __init__(self, *, repository: GameRepository) -> None:
        self._repository = repository

    def execute(self, request: CommandRequest) -> CommandResult:
        session = self._repository.load_session(request.save_id)
        new_session, event, result = session.apply_player_command(request)
        self._repository.save_session(new_session)
        self._repository.append_event(request.save_id, event)
        return result

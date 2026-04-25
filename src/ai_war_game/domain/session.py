"""GameSession 聚合: 会话元数据 + 玩家身份 + 剧本 + 世界。"""

import uuid
from dataclasses import dataclass, replace
from datetime import datetime

from ai_war_game.domain.command import CommandRequest, CommandResult
from ai_war_game.domain.events import GameEvent
from ai_war_game.domain.identity import PlayerIdentity
from ai_war_game.domain.scenario import Scenario
from ai_war_game.domain.world import WorldState

SCHEMA_VERSION = 1


@dataclass(frozen=True, slots=True)
class GameSession:
    """聚合根。第一版仅承担"接收命令 → 推进 1 天 → 返回事件"。"""

    save_id: str
    created_at: datetime
    updated_at: datetime
    player: PlayerIdentity
    scenario: Scenario
    world: WorldState
    schema_version: int = SCHEMA_VERSION

    def __post_init__(self) -> None:
        if not self.save_id.strip():
            raise ValueError("save_id 不能为空")
        if self.player.faction_id not in {f.faction_id for f in self.world.factions}:
            raise ValueError(f"玩家所属势力 {self.player.faction_id} 不在 world.factions 中")

    def apply_player_command(
        self, request: CommandRequest
    ) -> tuple["GameSession", GameEvent, CommandResult]:
        if request.save_id != self.save_id:
            raise ValueError(f"command.save_id={request.save_id} 与会话不一致 ({self.save_id})")
        if request.player_id != self.player.player_id:
            raise ValueError(
                f"command.player_id={request.player_id} 与会话不一致 ({self.player.player_id})"
            )
        new_world = self.world.advance_day()
        event = GameEvent(
            event_id=uuid.uuid4().hex,
            kind="player_action_logged",
            day=new_world.current_day,
            occurred_at=request.issued_at,
            payload={"text": request.text, "player_id": request.player_id},
        )
        new_session = replace(
            self,
            world=new_world,
            updated_at=request.issued_at,
        )
        result = CommandResult(
            save_id=self.save_id,
            accepted=True,
            message=f"命令已记录，进入第 {new_world.current_day} 天。",  # noqa: RUF001
            new_day=new_world.current_day,
        )
        return new_session, event, result

"""统一外部入口的命令封装。"""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from ai_war_game.domain.command import CommandRequest


class CommandSource(StrEnum):
    CLI = "CLI"
    WECHAT = "WECHAT"
    HERMES = "HERMES"


@dataclass(frozen=True, slots=True)
class CommandEnvelope:
    source: CommandSource
    player_id: str
    save_id: str
    command_text: str
    timestamp: datetime

    def __post_init__(self) -> None:
        if not self.player_id.strip():
            raise ValueError("player_id")
        if not self.save_id.strip():
            raise ValueError("save_id")
        if not self.command_text.strip():
            raise ValueError("command_text")

    def to_command_request(self) -> CommandRequest:
        return CommandRequest(
            save_id=self.save_id,
            player_id=self.player_id,
            text=self.command_text,
            issued_at=self.timestamp,
        )

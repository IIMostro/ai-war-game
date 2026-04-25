"""玩家命令的请求与结果模型。"""

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class CommandRequest:
    save_id: str
    player_id: str
    text: str
    issued_at: datetime

    def __post_init__(self) -> None:
        if not self.save_id.strip():
            raise ValueError("save_id 不能为空")
        if not self.player_id.strip():
            raise ValueError("player_id 不能为空")
        if not self.text.strip():
            raise ValueError("text 不能为空")


@dataclass(frozen=True, slots=True)
class CommandResult:
    save_id: str
    accepted: bool
    message: str
    new_day: int

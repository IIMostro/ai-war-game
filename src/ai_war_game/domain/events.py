"""游戏事件日志条目。"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass(frozen=True, slots=True)
class GameEvent:
    event_id: str
    kind: str
    day: int
    occurred_at: datetime
    payload: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.event_id.strip():
            raise ValueError("event_id 不能为空")
        if not self.kind.strip():
            raise ValueError("kind 不能为空")

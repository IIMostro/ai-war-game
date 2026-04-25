"""服务层公开的输入输出 DTO。"""

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class CreateGameInput:
    save_id: str
    theme: str
    player_id: str
    player_display_name: str
    issued_at: datetime


@dataclass(frozen=True, slots=True)
class CreateGameOutput:
    save_id: str
    starting_day: int
    summary: str


@dataclass(frozen=True, slots=True)
class ShowGameOutput:
    save_id: str
    current_day: int
    player_display_name: str
    faction_name: str
    summary: str
    recent_events: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class SaveSummary:
    save_id: str
    created_at: datetime
    updated_at: datetime
    current_day: int
    player_display_name: str

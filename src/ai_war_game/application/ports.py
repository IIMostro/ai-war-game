"""应用层依赖的外部能力契约（Protocol）。"""  # noqa: RUF002

from typing import Protocol, runtime_checkable

from ai_war_game.domain.events import GameEvent
from ai_war_game.domain.scenario import Scenario
from ai_war_game.domain.session import GameSession


@runtime_checkable
class HermesHealth(Protocol):
    def check(self) -> bool: ...


@runtime_checkable
class ScenarioGenerator(Protocol):
    def generate(self, *, theme: str, player_display_name: str) -> Scenario: ...


@runtime_checkable
class GameRepository(Protocol):
    def save_session(self, session: GameSession) -> None: ...
    def load_session(self, save_id: str) -> GameSession: ...
    def append_event(self, save_id: str, event: GameEvent) -> None: ...
    def list_save_ids(self) -> list[str]: ...
    def events(self, save_id: str) -> list[GameEvent]: ...
